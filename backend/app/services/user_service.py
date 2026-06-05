from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from threading import Lock
from typing import Optional
from urllib.parse import unquote, urlparse
from uuid import uuid4

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.schemas import (
    AISearchResponse,
    AISearchSessionStatus,
    AISessionSummary,
    AuthLoginResponse,
    AuthTotpChallengeResponse,
    AuthTokenResponse,
    BookingCreateResponse,
    DeviceInfo,
    EmailVerificationPurpose,
    FavoriteCreateResponse,
    RoutePlan,
    SessionDuration,
    TotpSetupResponse,
    UserPreferences,
    UserPreferencesUpdate,
    UserProfile,
)


RESET_CODE = "000000"
RESET_CODE_TTL_SECONDS = 60
TOTP_CHALLENGE_TTL_SECONDS = 300
PASSWORD_ITERATIONS = 120_000
APP_TIMEZONE = timezone(timedelta(hours=8))
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
AUDIT_EVENTS = {
    "login_success",
    "login_failed",
    "register_success",
    "register_failed",
    "email_changed",
    "password_changed",
    "account_deleted",
    "device_revoked",
    "totp_enabled",
    "totp_disabled",
    "totp_login_failed",
    "totp_email_code_replacement_updated",
}
SESSION_DURATION_DELTAS: dict[SessionDuration, Optional[timedelta]] = {
    "day": timedelta(days=1),
    "week": timedelta(days=7),
    "month": timedelta(days=30),
    "half_year": timedelta(days=180),
    "year": timedelta(days=365),
    "forever": None,
}

_bearer = HTTPBearer(auto_error=False)


class UserServiceError(RuntimeError):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class AuthenticatedUser:
    user: UserProfile
    token_hash: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _user_id_timestamp(created_at: datetime) -> str:
    return created_at.replace(tzinfo=timezone.utc).astimezone(APP_TIMEZONE).strftime("%Y%m%d%H%M%S")


def _user_id_from_existing(timestamp: str, existing_ids) -> str:
    prefix = f"user_{timestamp}"
    suffixes: list[int] = []
    for existing_id in existing_ids:
        if not isinstance(existing_id, str) or not existing_id.startswith(prefix):
            continue
        suffix_text = existing_id[len(prefix):]
        if suffix_text.isdigit():
            suffixes.append(int(suffix_text))
    suffix = 0 if not suffixes else max(suffixes) + 1
    return f"{prefix}{suffix}"


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _client_ip(request: Optional[Request]) -> str:
    if not request or not request.client:
        return "unknown"
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or request.client.host
    return request.client.host


def _is_production() -> bool:
    return settings.app_env.lower() == "production"


def _bearer_auth_enabled() -> bool:
    return not (_is_production() and settings.disable_bearer_auth_in_production)


def _cookie_max_age(expires_at: Optional[datetime]) -> Optional[int]:
    if expires_at is None:
        return None
    return max(0, int((expires_at - _utcnow()).total_seconds()))


def _csrf_signature(token_hash: str, nonce: str) -> str:
    digest = hmac.new(
        settings.csrf_secret.encode("utf-8"),
        f"{token_hash}.{nonce}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest


def _create_csrf_token(session_token: str) -> str:
    nonce = secrets.token_urlsafe(16)
    signature = _csrf_signature(_token_hash(session_token), nonce)
    return f"{nonce}.{signature}"


def _verify_csrf_token(*, session_token: str, csrf_token: str) -> bool:
    try:
        nonce, signature = csrf_token.split(".", 1)
    except ValueError:
        return False
    expected = _csrf_signature(_token_hash(session_token), nonce)
    return secrets.compare_digest(signature, expected)


def _totp_fernet() -> Fernet:
    key = hashlib.sha256(settings.totp_encryption_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _encrypt_totp_secret(secret: str) -> str:
    return _totp_fernet().encrypt(secret.encode("ascii")).decode("ascii")


def _decrypt_totp_secret(secret_encrypted: str) -> str:
    try:
        return _totp_fernet().decrypt(secret_encrypted.encode("ascii")).decode("ascii")
    except (InvalidToken, ValueError) as exc:
        raise UserServiceError("Unable to read TOTP configuration.", status.HTTP_500_INTERNAL_SERVER_ERROR) from exc


def set_auth_cookies(response: Response, token: str, expires_at: Optional[datetime]) -> str:
    csrf_token = _create_csrf_token(token)
    max_age = _cookie_max_age(expires_at)
    cookie_expires = expires_at.replace(tzinfo=timezone.utc) if expires_at is not None else None
    same_site = settings.session_cookie_samesite.lower()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=same_site,
        max_age=max_age,
        expires=cookie_expires,
        path="/",
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite=same_site,
        max_age=max_age,
        expires=cookie_expires,
        path="/",
    )
    return csrf_token


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.auth_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return (
        f"pbkdf2_sha256${PASSWORD_ITERATIONS}$"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(digest).decode('ascii')}"
    )


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_text.encode("ascii"))
        expected = base64.b64decode(digest_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations),
        )
        return secrets.compare_digest(actual, expected)
    except Exception:
        return False


def _parse_database_url(database_url: str) -> dict[str, object]:
    parsed = urlparse(database_url)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or "root"),
        "password": unquote(parsed.password or ""),
        "database": parsed.path.lstrip("/"),
    }


def _json_dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_load(value: object, default):
    if not value:
        return default
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


class UserService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._mysql_config = _parse_database_url(settings.database_url)
        self._mysql_available = self._initialize_mysql()

        self._users: dict[str, dict] = {}
        self._email_index: dict[str, str] = {}
        self._tokens: dict[str, dict] = {}
        self._preferences: dict[str, UserPreferences] = {}
        self._favorites: dict[str, dict[str, dict]] = {}
        self._devices: dict[str, dict[str, dict]] = {}
        self._reset_by_email: dict[str, dict] = {}
        self._reset_tokens: dict[str, dict] = {}
        self._email_verifications: dict[tuple[str, EmailVerificationPurpose], dict] = {}
        self._email_verification_tokens: dict[str, dict] = {}
        self._avatars: dict[str, tuple[str, bytes]] = {}
        self._ai_sessions: dict[str, dict[str, dict]] = {}
        self._bookings: dict[str, dict] = {}
        self._rate_limits: dict[str, list[datetime]] = {}
        self._audit_logs: list[dict] = []
        self._totp_settings: dict[str, dict] = {}
        self._totp_challenges: dict[str, dict] = {}

        if _is_production() and not self._mysql_available:
            raise RuntimeError("MySQL is required for account storage in production.")
        if _is_production():
            if not settings.session_cookie_secret or settings.session_cookie_secret == "dev-session-cookie-secret":
                raise RuntimeError("SESSION_COOKIE_SECRET must be configured in production.")
            if not settings.csrf_secret or settings.csrf_secret == "dev-csrf-secret":
                raise RuntimeError("CSRF_SECRET must be configured in production.")
            if not settings.totp_encryption_secret or settings.totp_encryption_secret == "dev-totp-encryption-secret":
                raise RuntimeError("TOTP_ENCRYPTION_SECRET must be configured in production.")

    def _connect(self):
        import mysql.connector

        return mysql.connector.connect(
            host=self._mysql_config["host"],
            port=self._mysql_config["port"],
            user=self._mysql_config["user"],
            password=self._mysql_config["password"],
            database=self._mysql_config["database"],
            charset="utf8mb4",
            collation="utf8mb4_general_ci",
            use_unicode=True,
        )

    def _initialize_mysql(self) -> bool:
        try:
            import mysql.connector  # noqa: F401

            connection = self._connect()
        except Exception:
            return False

        statements = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(40) PRIMARY KEY,
                username VARCHAR(80) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                email_verified BOOLEAN NOT NULL DEFAULT TRUE,
                totp_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                totp_replaces_email_codes BOOLEAN NOT NULL DEFAULT FALSE,
                nickname VARCHAR(80),
                avatar_url VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token_hash CHAR(64) PRIMARY KEY,
                user_id VARCHAR(40) NOT NULL,
                device_id VARCHAR(40) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NULL,
                revoked_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS user_devices (
                id VARCHAR(40) PRIMARY KEY,
                user_id VARCHAR(40) NOT NULL,
                token_hash CHAR(64),
                device_name VARCHAR(255) NOT NULL,
                ip_address VARCHAR(80) NOT NULL,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                revoked_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                email VARCHAR(255) PRIMARY KEY,
                code VARCHAR(20) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                reset_token VARCHAR(120),
                verified_at TIMESTAMP NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS email_verification_tokens (
                email VARCHAR(255) NOT NULL,
                purpose VARCHAR(40) NOT NULL,
                code VARCHAR(20) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                verification_token VARCHAR(120),
                verified_at TIMESTAMP NULL,
                PRIMARY KEY (email, purpose)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id VARCHAR(40) PRIMARY KEY,
                theme VARCHAR(10) NOT NULL DEFAULT 'light',
                language VARCHAR(10) NOT NULL DEFAULT 'zh',
                search_retention_days INT NOT NULL DEFAULT 30,
                chat_retention_days INT NOT NULL DEFAULT 30,
                import_platforms TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS user_favorites (
                id VARCHAR(40) PRIMARY KEY,
                user_id VARCHAR(40) NOT NULL,
                route_id VARCHAR(255) NOT NULL,
                route_json MEDIUMTEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_user_route (user_id, route_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS user_avatars (
                user_id VARCHAR(40) PRIMARY KEY,
                content_type VARCHAR(120) NOT NULL,
                data LONGBLOB NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS ai_search_sessions (
                session_id VARCHAR(80) PRIMARY KEY,
                user_id VARCHAR(40) NOT NULL,
                title VARCHAR(120) NOT NULL,
                status VARCHAR(40) NOT NULL,
                last_message_preview VARCHAR(255) NOT NULL,
                response_json MEDIUMTEXT NOT NULL,
                active_run_id VARCHAR(100),
                active_run_started_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS ai_agent_usage (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(40) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_ai_usage_user_time (user_id, created_at),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS ai_agent_requests (
                request_id VARCHAR(100) PRIMARY KEY,
                user_id VARCHAR(40) NOT NULL,
                session_id VARCHAR(80) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_ai_request_session (session_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES ai_search_sessions(session_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS ai_checkpoint_deletions (
                session_id VARCHAR(80) PRIMARY KEY,
                user_id VARCHAR(40) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                last_error VARCHAR(255)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS bookings (
                booking_id VARCHAR(40) PRIMARY KEY,
                user_id VARCHAR(40) NOT NULL,
                route_id VARCHAR(255) NOT NULL,
                legs_json MEDIUMTEXT NOT NULL,
                status VARCHAR(40) NOT NULL,
                redirect_url VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS security_audit_logs (
                id VARCHAR(40) PRIMARY KEY,
                user_id VARCHAR(40),
                event_type VARCHAR(80) NOT NULL,
                ip_address VARCHAR(80) NOT NULL,
                device_name VARCHAR(255),
                success BOOLEAN NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT NOT NULL,
                INDEX idx_audit_user_time (user_id, created_at),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS user_totp_settings (
                user_id VARCHAR(40) PRIMARY KEY,
                secret_encrypted TEXT NOT NULL,
                enabled BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS totp_login_challenges (
                challenge_hash CHAR(64) PRIMARY KEY,
                user_id VARCHAR(40) NOT NULL,
                session_duration VARCHAR(20) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                consumed_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        ]
        try:
            cursor = connection.cursor()
            for statement in statements:
                cursor.execute(statement)
            self._ensure_mysql_column(cursor, "users", "email_verified", "BOOLEAN NOT NULL DEFAULT TRUE AFTER password_hash")
            self._ensure_mysql_column(cursor, "users", "totp_enabled", "BOOLEAN NOT NULL DEFAULT FALSE AFTER email_verified")
            self._ensure_mysql_column(
                cursor,
                "users",
                "totp_replaces_email_codes",
                "BOOLEAN NOT NULL DEFAULT FALSE AFTER totp_enabled",
            )
            self._ensure_mysql_column(cursor, "auth_tokens", "expires_at", "TIMESTAMP NULL AFTER created_at")
            self._ensure_mysql_column(cursor, "ai_search_sessions", "active_run_id", "VARCHAR(100) NULL AFTER response_json")
            self._ensure_mysql_column(
                cursor,
                "ai_search_sessions",
                "active_run_started_at",
                "TIMESTAMP NULL AFTER active_run_id",
            )
            cursor.execute("UPDATE ai_search_sessions SET response_json = '{}' WHERE response_json <> '{}'")
            connection.commit()
            return True
        except Exception:
            return False
        finally:
            connection.close()

    @staticmethod
    def _ensure_mysql_column(cursor, table_name: str, column_name: str, column_definition: str) -> None:
        cursor.execute(f"SHOW COLUMNS FROM {table_name} LIKE %s", (column_name,))
        if cursor.fetchone():
            return
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")

    def _check_rate_limit(self, scope: str, identifier: str, *, limit: int, window_seconds: Optional[int] = None) -> None:
        if not identifier:
            identifier = "unknown"
        window = timedelta(seconds=window_seconds or settings.rate_limit_window_seconds)
        now = _utcnow()
        key = f"{scope}:{identifier}"
        with self._lock:
            attempts = [
                attempt
                for attempt in self._rate_limits.get(key, [])
                if now - attempt < window
            ]
            if len(attempts) >= limit:
                self._rate_limits[key] = attempts
                raise UserServiceError("Too many attempts. Please try again later.", status.HTTP_429_TOO_MANY_REQUESTS)
            attempts.append(now)
            self._rate_limits[key] = attempts

    def _record_audit_event(
        self,
        *,
        event_type: str,
        user_id: Optional[str],
        request: Optional[Request],
        success: bool,
        metadata: Optional[dict] = None,
    ) -> None:
        if event_type not in AUDIT_EVENTS:
            return
        audit_id = f"audit_{uuid4().hex}"
        created_at = _utcnow()
        ip_address = _client_ip(request)
        device_name = request.headers.get("user-agent", "Unknown device")[:255] if request else "Unknown device"
        clean_metadata = {
            key: value
            for key, value in (metadata or {}).items()
            if key not in {"password", "token", "code", "access_token", "verification_token", "reset_token"}
        }

        if self._mysql_available:
            try:
                with self._connect() as connection:
                    cursor = connection.cursor()
                    cursor.execute(
                        """
                        INSERT INTO security_audit_logs (
                            id, user_id, event_type, ip_address, device_name,
                            success, created_at, metadata_json
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            audit_id,
                            user_id,
                            event_type,
                            ip_address,
                            device_name,
                            success,
                            created_at,
                            _json_dump(clean_metadata),
                        ),
                    )
                    connection.commit()
            except Exception:
                return
            return

        with self._lock:
            self._audit_logs.append(
                {
                    "id": audit_id,
                    "user_id": user_id,
                    "event_type": event_type,
                    "ip_address": ip_address,
                    "device_name": device_name,
                    "success": success,
                    "created_at": created_at,
                    "metadata": clean_metadata,
                }
            )

    @staticmethod
    def _next_user_id_mysql(cursor, timestamp: str) -> str:
        prefix = f"user_{timestamp}"
        cursor.execute("SELECT id FROM users WHERE id LIKE %s", (f"{prefix}%",))
        rows = cursor.fetchall()
        return _user_id_from_existing(timestamp, [row[0] for row in rows])

    def register(
        self,
        *,
        username: str,
        email: str,
        password: str,
        email_verification_token: str,
        session_duration: SessionDuration = "day",
        request: Optional[Request] = None,
    ) -> AuthTokenResponse:
        email = _normalize_email(email)
        self._check_rate_limit("register:ip", _client_ip(request), limit=100)
        self._check_rate_limit("register:email", email, limit=5)
        profile: Optional[UserProfile] = None
        try:
            self._consume_email_verification_token(
                email=email,
                purpose="register",
                verification_token=email_verification_token,
            )
            created_at = _utcnow()
            user_id_timestamp = _user_id_timestamp(created_at)
            initial_nickname = username.strip()
            password_hash = _hash_password(password)

            if self._mysql_available:
                try:
                    with self._connect() as connection:
                        cursor = connection.cursor()
                        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                        if cursor.fetchone():
                            raise UserServiceError("Email is already registered.", status.HTTP_409_CONFLICT)
                        for _ in range(1000):
                            user_id = self._next_user_id_mysql(cursor, user_id_timestamp)
                            profile = UserProfile(
                                id=user_id,
                                username=user_id,
                                email=email,
                                email_verified=True,
                                totp_enabled=False,
                                totp_replaces_email_codes=False,
                                nickname=initial_nickname,
                                avatar_url=None,
                                created_at=created_at,
                            )
                            try:
                                cursor.execute(
                                    """
                                    INSERT INTO users (
                                        id, username, email, password_hash,
                                        email_verified, nickname, created_at
                                    )
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """,
                                    (
                                        profile.id,
                                        profile.username,
                                        profile.email,
                                        password_hash,
                                        True,
                                        profile.nickname,
                                        created_at,
                                    ),
                                )
                                break
                            except Exception as exc:
                                if "PRIMARY" in str(exc).upper():
                                    continue
                                raise
                        else:
                            raise UserServiceError("Unable to generate user id.", status.HTTP_500_INTERNAL_SERVER_ERROR)
                        self._ensure_preferences_mysql(cursor, profile.id)
                        connection.commit()
                except Exception as exc:
                    if isinstance(exc, UserServiceError):
                        raise exc
                    raise UserServiceError("Email is already registered.", status.HTTP_409_CONFLICT) from exc
            else:
                with self._lock:
                    if email in self._email_index:
                        raise UserServiceError("Email is already registered.", status.HTTP_409_CONFLICT)
                    user_id = _user_id_from_existing(user_id_timestamp, self._users.keys())
                    profile = UserProfile(
                        id=user_id,
                        username=user_id,
                        email=email,
                        email_verified=True,
                        totp_enabled=False,
                        totp_replaces_email_codes=False,
                        nickname=initial_nickname,
                        avatar_url=None,
                        created_at=created_at,
                    )
                    self._users[user_id] = {
                        "profile": profile,
                        "password_hash": password_hash,
                    }
                    self._email_index[email] = user_id
                    self._preferences[user_id] = UserPreferences()

            self._record_audit_event(
                event_type="register_success",
                user_id=profile.id if profile else None,
                request=request,
                success=True,
            )
            return self._issue_token(profile, session_duration=session_duration, request=request)
        except Exception:
            self._record_audit_event(
                event_type="register_failed",
                user_id=None,
                request=request,
                success=False,
                metadata={"email_domain": email.split("@")[-1] if "@" in email else ""},
            )
            raise

    def login(
        self,
        *,
        email: str,
        password: str,
        session_duration: SessionDuration = "day",
        request: Optional[Request] = None,
    ) -> AuthLoginResponse:
        email = _normalize_email(email)
        self._check_rate_limit("login:ip", _client_ip(request), limit=60)
        self._check_rate_limit("login:email", email, limit=6)
        profile, password_hash = self._get_user_with_password(email)
        if profile is None or not _verify_password(password, password_hash or ""):
            self._record_audit_event(
                event_type="login_failed",
                user_id=profile.id if profile else None,
                request=request,
                success=False,
            )
            raise UserServiceError("Invalid email or password.", status.HTTP_401_UNAUTHORIZED)
        if profile.totp_enabled:
            return self._create_totp_login_challenge(profile.id, session_duration)
        self._record_audit_event(
            event_type="login_success",
            user_id=profile.id,
            request=request,
            success=True,
        )
        return self._issue_token(profile, session_duration=session_duration, request=request)

    def _create_totp_login_challenge(
        self,
        user_id: str,
        session_duration: SessionDuration,
    ) -> AuthTotpChallengeResponse:
        challenge_token = secrets.token_urlsafe(32)
        challenge_hash = _token_hash(challenge_token)
        expires_at = _utcnow() + timedelta(seconds=TOTP_CHALLENGE_TTL_SECONDS)
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO totp_login_challenges (
                        challenge_hash, user_id, session_duration, expires_at
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (challenge_hash, user_id, session_duration, expires_at),
                )
                connection.commit()
        else:
            with self._lock:
                self._totp_challenges[challenge_hash] = {
                    "user_id": user_id,
                    "session_duration": session_duration,
                    "expires_at": expires_at,
                    "consumed_at": None,
                }
        return AuthTotpChallengeResponse(
            challenge_token=challenge_token,
            expires_in_seconds=TOTP_CHALLENGE_TTL_SECONDS,
        )

    def complete_totp_login(
        self,
        *,
        challenge_token: str,
        code: str,
        request: Optional[Request] = None,
    ) -> AuthTokenResponse:
        challenge_hash = _token_hash(challenge_token)
        self._check_rate_limit("totp_login:challenge", challenge_hash, limit=8)
        now = _utcnow()
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT user_id, session_duration, expires_at, consumed_at
                    FROM totp_login_challenges
                    WHERE challenge_hash = %s
                    """,
                    (challenge_hash,),
                )
                challenge = cursor.fetchone()
        else:
            challenge = self._totp_challenges.get(challenge_hash)
        if (
            not challenge
            or challenge.get("consumed_at") is not None
            or challenge["expires_at"] <= now
        ):
            raise UserServiceError("Invalid or expired TOTP challenge.", status.HTTP_401_UNAUTHORIZED)
        user_id = challenge["user_id"]
        if not self.verify_totp_code(user_id, code):
            self._record_audit_event(
                event_type="totp_login_failed",
                user_id=user_id,
                request=request,
                success=False,
            )
            raise UserServiceError("Invalid authentication code.", status.HTTP_401_UNAUTHORIZED)

        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    UPDATE totp_login_challenges
                    SET consumed_at = %s
                    WHERE challenge_hash = %s
                      AND consumed_at IS NULL
                      AND expires_at > %s
                    """,
                    (now, challenge_hash, now),
                )
                if cursor.rowcount != 1:
                    connection.rollback()
                    raise UserServiceError("Invalid or expired TOTP challenge.", status.HTTP_401_UNAUTHORIZED)
                connection.commit()
        else:
            with self._lock:
                current_challenge = self._totp_challenges.get(challenge_hash)
                if (
                    not current_challenge
                    or current_challenge.get("consumed_at") is not None
                    or current_challenge["expires_at"] <= now
                ):
                    raise UserServiceError("Invalid or expired TOTP challenge.", status.HTTP_401_UNAUTHORIZED)
                current_challenge["consumed_at"] = now

        profile = self.get_profile(user_id)
        self._record_audit_event(
            event_type="login_success",
            user_id=user_id,
            request=request,
            success=True,
            metadata={"factor": "totp"},
        )
        return self._issue_token(
            profile,
            session_duration=challenge["session_duration"],
            request=request,
        )

    def logout(self, token_hash: str) -> None:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "UPDATE auth_tokens SET revoked_at = %s WHERE token_hash = %s",
                    (_utcnow(), token_hash),
                )
                cursor.execute(
                    "UPDATE user_devices SET revoked_at = %s WHERE token_hash = %s",
                    (_utcnow(), token_hash),
                )
                connection.commit()
            return

        with self._lock:
            token = self._tokens.get(token_hash)
            if token:
                token["revoked_at"] = _utcnow()
                device = self._devices.get(token["user_id"], {}).get(token["device_id"])
                if device:
                    device["revoked_at"] = _utcnow()

    def update_current_session_duration(
        self,
        user_id: str,
        token_hash: str,
        session_duration: SessionDuration,
    ) -> Optional[datetime]:
        now = _utcnow()
        delta = SESSION_DURATION_DELTAS[session_duration]
        expires_at = now + delta if delta is not None else None

        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    UPDATE auth_tokens
                    SET expires_at = %s
                    WHERE token_hash = %s
                      AND user_id = %s
                      AND revoked_at IS NULL
                      AND (expires_at IS NULL OR expires_at > %s)
                    """,
                    (expires_at, token_hash, user_id, now),
                )
                if cursor.rowcount == 0:
                    raise UserServiceError("Invalid or expired token.", status.HTTP_401_UNAUTHORIZED)
                connection.commit()
            return expires_at

        with self._lock:
            token_record = self._tokens.get(token_hash)
            if (
                not token_record
                or token_record.get("user_id") != user_id
                or token_record.get("revoked_at") is not None
                or (
                    token_record.get("expires_at") is not None
                    and token_record["expires_at"] <= now
                )
            ):
                raise UserServiceError("Invalid or expired token.", status.HTTP_401_UNAUTHORIZED)
            token_record["expires_at"] = expires_at
            return expires_at

    def authenticate_token(self, token: str) -> AuthenticatedUser:
        token_hash = _token_hash(token)
        now = _utcnow()
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT u.id, u.username, u.email, u.email_verified, u.totp_enabled,
                           u.totp_replaces_email_codes, u.nickname, u.avatar_url, u.created_at
                    FROM auth_tokens t
                    JOIN users u ON u.id = t.user_id
                    WHERE t.token_hash = %s
                      AND t.revoked_at IS NULL
                      AND (t.expires_at IS NULL OR t.expires_at > %s)
                    """,
                    (token_hash, now),
                )
                row = cursor.fetchone()
                if row:
                    cursor = connection.cursor()
                    cursor.execute(
                        "UPDATE user_devices SET login_time = %s WHERE token_hash = %s AND revoked_at IS NULL",
                        (now, token_hash),
                    )
                    connection.commit()
            if not row:
                raise UserServiceError("Invalid or expired token.", status.HTTP_401_UNAUTHORIZED)
            return AuthenticatedUser(user=self._profile_from_row(row), token_hash=token_hash)

        with self._lock:
            token_record = self._tokens.get(token_hash)
            expires_at = token_record.get("expires_at") if token_record else None
            if (
                not token_record
                or token_record.get("revoked_at") is not None
                or (expires_at is not None and expires_at <= now)
            ):
                raise UserServiceError("Invalid or expired token.", status.HTTP_401_UNAUTHORIZED)
            device = self._devices.get(token_record["user_id"], {}).get(token_record["device_id"])
            if device and device.get("revoked_at") is None:
                device["login_time"] = now
            user_record = self._users[token_record["user_id"]]
            return AuthenticatedUser(user=user_record["profile"], token_hash=token_hash)

    def get_profile(self, user_id: str) -> UserProfile:
        profile = self._get_profile_by_id(user_id)
        if profile is None:
            raise UserServiceError("User not found.", status.HTTP_404_NOT_FOUND)
        return profile

    def update_profile(self, user_id: str, *, nickname: Optional[str]) -> UserProfile:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute("UPDATE users SET nickname = %s WHERE id = %s", (nickname, user_id))
                connection.commit()
            return self.get_profile(user_id)

        with self._lock:
            profile = self._users[user_id]["profile"]
            self._users[user_id]["profile"] = profile.model_copy(update={"nickname": nickname})
            return self._users[user_id]["profile"]

    def delete_account(self, user_id: str, *, request: Optional[Request] = None) -> None:
        self._check_rate_limit("account_delete:user", user_id, limit=3)
        if self._mysql_available:
            self.get_profile(user_id)
            self._record_audit_event(
                event_type="account_deleted",
                user_id=user_id,
                request=request,
                success=True,
            )
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
                if cursor.rowcount == 0:
                    raise UserServiceError("User not found.", status.HTTP_404_NOT_FOUND)
                connection.commit()
            return

        with self._lock:
            user_record = self._users.pop(user_id, None)
            if not user_record:
                raise UserServiceError("User not found.", status.HTTP_404_NOT_FOUND)
            self._email_index.pop(user_record["profile"].email, None)
            self._preferences.pop(user_id, None)
            self._favorites.pop(user_id, None)
            self._devices.pop(user_id, None)
            self._avatars.pop(user_id, None)
            self._totp_settings.pop(user_id, None)
            self._ai_sessions.pop(user_id, None)
            self._bookings = {
                booking_id: booking
                for booking_id, booking in self._bookings.items()
                if booking.get("user_id") != user_id
            }
            self._tokens = {
                token_hash: token
                for token_hash, token in self._tokens.items()
                if token.get("user_id") != user_id
            }
            self._totp_challenges = {
                challenge_hash: challenge
                for challenge_hash, challenge in self._totp_challenges.items()
                if challenge.get("user_id") != user_id
            }
        self._record_audit_event(
            event_type="account_deleted",
            user_id=user_id,
            request=request,
            success=True,
        )

    def update_avatar(self, user_id: str, *, content_type: str, data: bytes) -> str:
        avatar_url = f"/api/v1/user/avatar/{user_id}"
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO user_avatars (user_id, content_type, data)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE content_type = VALUES(content_type), data = VALUES(data)
                    """,
                    (user_id, content_type, data),
                )
                cursor.execute("UPDATE users SET avatar_url = %s WHERE id = %s", (avatar_url, user_id))
                connection.commit()
            return avatar_url

        with self._lock:
            self._avatars[user_id] = (content_type, data)
            profile = self._users[user_id]["profile"]
            self._users[user_id]["profile"] = profile.model_copy(update={"avatar_url": avatar_url})
        return avatar_url

    def update_avatar_preset(self, user_id: str, *, preset_id: str) -> UserProfile:
        avatar_url = f"material:{preset_id}"
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute("UPDATE users SET avatar_url = %s WHERE id = %s", (avatar_url, user_id))
                connection.commit()
            return self.get_profile(user_id)

        with self._lock:
            if user_id not in self._users:
                raise UserServiceError("User not found.", status.HTTP_404_NOT_FOUND)
            profile = self._users[user_id]["profile"]
            self._users[user_id]["profile"] = profile.model_copy(update={"avatar_url": avatar_url})
            return self._users[user_id]["profile"]

    def get_avatar(self, user_id: str) -> tuple[str, bytes]:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SELECT content_type, data FROM user_avatars WHERE user_id = %s", (user_id,))
                row = cursor.fetchone()
            if not row:
                raise UserServiceError("Avatar not found.", status.HTTP_404_NOT_FOUND)
            return row["content_type"], row["data"]

        avatar = self._avatars.get(user_id)
        if not avatar:
            raise UserServiceError("Avatar not found.", status.HTTP_404_NOT_FOUND)
        return avatar

    def update_email(
        self,
        user_id: str,
        *,
        new_email: str,
        current_email: str,
        verification_token: str,
        request: Optional[Request] = None,
    ) -> UserProfile:
        self._check_rate_limit("email_update:user", user_id, limit=8)
        profile = self.get_profile(user_id)
        if _normalize_email(current_email) != profile.email:
            raise UserServiceError("Current email confirmation does not match.", status.HTTP_400_BAD_REQUEST)
        email = _normalize_email(new_email)
        if email == profile.email:
            raise UserServiceError("New email must be different from the current email.", status.HTTP_400_BAD_REQUEST)
        self._consume_email_verification_token(
            email=email,
            purpose="change_email",
            verification_token=verification_token,
        )
        if self._mysql_available:
            try:
                with self._connect() as connection:
                    cursor = connection.cursor()
                    cursor.execute("UPDATE users SET email = %s, email_verified = TRUE WHERE id = %s", (email, user_id))
                    connection.commit()
            except Exception as exc:
                if "1062" in str(exc) or "Duplicate entry" in str(exc):
                    raise UserServiceError("Email is already registered.", status.HTTP_409_CONFLICT) from exc
                raise UserServiceError("Unable to update email.", status.HTTP_500_INTERNAL_SERVER_ERROR) from exc
            self._record_audit_event(
                event_type="email_changed",
                user_id=user_id,
                request=request,
                success=True,
            )
            return self.get_profile(user_id)

        with self._lock:
            if email in self._email_index and self._email_index[email] != user_id:
                raise UserServiceError("Email is already registered.", status.HTTP_409_CONFLICT)
            profile = self._users[user_id]["profile"]
            self._email_index.pop(profile.email, None)
            self._email_index[email] = user_id
            self._users[user_id]["profile"] = profile.model_copy(update={"email": email, "email_verified": True})
            updated_profile = self._users[user_id]["profile"]
        self._record_audit_event(
            event_type="email_changed",
            user_id=user_id,
            request=request,
            success=True,
        )
        return updated_profile

    def update_password(self, user_id: str, *, current_password: str, new_password: str, request: Optional[Request] = None) -> None:
        self._check_rate_limit("password_update:user", user_id, limit=8)
        profile = self.get_profile(user_id)
        _, current_hash = self._get_user_with_password(profile.email)
        if not _verify_password(current_password, current_hash or ""):
            raise UserServiceError("Current password is incorrect.", status.HTTP_400_BAD_REQUEST)
        self._set_password(user_id, _hash_password(new_password))
        self._record_audit_event(
            event_type="password_changed",
            user_id=user_id,
            request=request,
            success=True,
        )

    def revoke_other_tokens(self, user_id: str, current_token_hash: str) -> None:
        now = _utcnow()
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    UPDATE auth_tokens
                    SET revoked_at = %s
                    WHERE user_id = %s AND token_hash <> %s AND revoked_at IS NULL
                    """,
                    (now, user_id, current_token_hash),
                )
                cursor.execute(
                    """
                    UPDATE user_devices
                    SET revoked_at = %s
                    WHERE user_id = %s AND token_hash <> %s AND revoked_at IS NULL
                    """,
                    (now, user_id, current_token_hash),
                )
                connection.commit()
            return

        with self._lock:
            for token_hash, token in self._tokens.items():
                if token.get("user_id") == user_id and token_hash != current_token_hash:
                    token["revoked_at"] = now
            for device in self._devices.get(user_id, {}).values():
                if device.get("token_hash") != current_token_hash:
                    device["revoked_at"] = now

    def check_password(self, user_id: str, current_password: str) -> bool:
        self._check_rate_limit("password_check:user", user_id, limit=20)
        profile = self.get_profile(user_id)
        _, current_hash = self._get_user_with_password(profile.email)
        return _verify_password(current_password, current_hash or "")

    def begin_totp_setup(self, user_id: str, *, current_password: str, request: Optional[Request] = None) -> TotpSetupResponse:
        self._check_rate_limit("totp_setup:user", user_id, limit=8)
        profile = self.get_profile(user_id)
        if profile.totp_enabled:
            raise UserServiceError("TOTP is already enabled.", status.HTTP_409_CONFLICT)
        _, current_hash = self._get_user_with_password(profile.email)
        if not _verify_password(current_password, current_hash or ""):
            raise UserServiceError("Current password is incorrect.", status.HTTP_400_BAD_REQUEST)

        secret = pyotp.random_base32()
        secret_encrypted = _encrypt_totp_secret(secret)
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO user_totp_settings (user_id, secret_encrypted, enabled)
                    VALUES (%s, %s, FALSE)
                    ON DUPLICATE KEY UPDATE secret_encrypted = VALUES(secret_encrypted), enabled = FALSE
                    """,
                    (user_id, secret_encrypted),
                )
                connection.commit()
        else:
            with self._lock:
                self._totp_settings[user_id] = {
                    "secret_encrypted": secret_encrypted,
                    "enabled": False,
                }

        uri = pyotp.TOTP(secret).provisioning_uri(
            name=profile.email,
            issuer_name=settings.totp_issuer_name,
        )
        return TotpSetupResponse(secret=secret, provisioning_uri=uri)

    def enable_totp(self, user_id: str, *, code: str, request: Optional[Request] = None) -> UserProfile:
        self._check_rate_limit("totp_enable:user", user_id, limit=8)
        setting = self._get_totp_setting(user_id)
        if not setting or setting["enabled"]:
            raise UserServiceError("No pending TOTP setup.", status.HTTP_400_BAD_REQUEST)
        secret = _decrypt_totp_secret(setting["secret_encrypted"])
        if not pyotp.TOTP(secret).verify(code.strip(), valid_window=1):
            raise UserServiceError("Invalid authentication code.", status.HTTP_400_BAD_REQUEST)
        self._set_totp_enabled(user_id, True)
        self._record_audit_event(
            event_type="totp_enabled",
            user_id=user_id,
            request=request,
            success=True,
        )
        return self.get_profile(user_id)

    def disable_totp(
        self,
        user_id: str,
        *,
        current_password: str,
        code: str,
        request: Optional[Request] = None,
    ) -> UserProfile:
        self._check_rate_limit("totp_disable:user", user_id, limit=8)
        profile = self.get_profile(user_id)
        _, current_hash = self._get_user_with_password(profile.email)
        if not _verify_password(current_password, current_hash or ""):
            raise UserServiceError("Current password is incorrect.", status.HTTP_400_BAD_REQUEST)
        if not self.verify_totp_code(user_id, code):
            raise UserServiceError("Invalid authentication code.", status.HTTP_400_BAD_REQUEST)
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute("DELETE FROM user_totp_settings WHERE user_id = %s", (user_id,))
                cursor.execute(
                    "UPDATE users SET totp_enabled = FALSE, totp_replaces_email_codes = FALSE WHERE id = %s",
                    (user_id,),
                )
                cursor.execute("DELETE FROM password_reset_tokens WHERE email = %s", (profile.email,))
                connection.commit()
        else:
            with self._lock:
                self._totp_settings.pop(user_id, None)
                profile = self._users[user_id]["profile"]
                self._users[user_id]["profile"] = profile.model_copy(
                    update={"totp_enabled": False, "totp_replaces_email_codes": False}
                )
                reset_record = self._reset_by_email.pop(profile.email, None)
                if reset_record and reset_record.get("reset_token"):
                    self._reset_tokens.pop(reset_record["reset_token"], None)
        self._record_audit_event(
            event_type="totp_disabled",
            user_id=user_id,
            request=request,
            success=True,
        )
        return self.get_profile(user_id)

    def verify_totp_code(self, user_id: str, code: str) -> bool:
        setting = self._get_totp_setting(user_id)
        if not setting or not setting["enabled"]:
            return False
        secret = _decrypt_totp_secret(setting["secret_encrypted"])
        return bool(pyotp.TOTP(secret).verify(code.strip(), valid_window=1))

    def update_totp_email_code_replacement(
        self,
        user_id: str,
        *,
        enabled: bool,
        request: Optional[Request] = None,
    ) -> UserProfile:
        profile = self.get_profile(user_id)
        if enabled and not profile.totp_enabled:
            raise UserServiceError("TOTP must be enabled first.", status.HTTP_409_CONFLICT)
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "UPDATE users SET totp_replaces_email_codes = %s WHERE id = %s",
                    (enabled, user_id),
                )
                cursor.execute("DELETE FROM password_reset_tokens WHERE email = %s", (profile.email,))
                connection.commit()
            updated = self.get_profile(user_id)
        else:
            with self._lock:
                updated = profile.model_copy(update={"totp_replaces_email_codes": enabled})
                self._users[user_id]["profile"] = updated
                reset_record = self._reset_by_email.pop(profile.email, None)
                if reset_record and reset_record.get("reset_token"):
                    self._reset_tokens.pop(reset_record["reset_token"], None)
        self._record_audit_event(
            event_type="totp_email_code_replacement_updated",
            user_id=user_id,
            request=request,
            success=True,
            metadata={"enabled": enabled},
        )
        return updated

    def _get_totp_setting(self, user_id: str) -> Optional[dict]:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    "SELECT secret_encrypted, enabled FROM user_totp_settings WHERE user_id = %s",
                    (user_id,),
                )
                row = cursor.fetchone()
            if not row:
                return None
            return {
                "secret_encrypted": row["secret_encrypted"],
                "enabled": bool(row["enabled"]),
            }
        return self._totp_settings.get(user_id)

    def _set_totp_enabled(self, user_id: str, enabled: bool) -> None:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute("UPDATE user_totp_settings SET enabled = %s WHERE user_id = %s", (enabled, user_id))
                cursor.execute(
                    """
                    UPDATE users
                    SET totp_enabled = %s,
                        totp_replaces_email_codes = CASE WHEN %s THEN totp_replaces_email_codes ELSE FALSE END
                    WHERE id = %s
                    """,
                    (enabled, enabled, user_id),
                )
                connection.commit()
            return
        with self._lock:
            self._totp_settings[user_id]["enabled"] = enabled
            profile = self._users[user_id]["profile"]
            self._users[user_id]["profile"] = profile.model_copy(
                update={
                    "totp_enabled": enabled,
                    "totp_replaces_email_codes": profile.totp_replaces_email_codes if enabled else False,
                }
            )

    def verify_current_email(self, user_id: str, *, verification_token: str) -> UserProfile:
        profile = self.get_profile(user_id)
        self._consume_email_verification_token(
            email=profile.email,
            purpose="verify_current",
            verification_token=verification_token,
        )
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute("UPDATE users SET email_verified = TRUE WHERE id = %s", (user_id,))
                connection.commit()
            return self.get_profile(user_id)

        with self._lock:
            self._users[user_id]["profile"] = profile.model_copy(update={"email_verified": True})
            return self._users[user_id]["profile"]

    def send_email_verification_code(self, *, email: str, purpose: EmailVerificationPurpose) -> int:
        email = _normalize_email(email)
        if purpose in {"register", "change_email"} and self.check_email(email):
            raise UserServiceError("Email is already registered.", status.HTTP_409_CONFLICT)
        if purpose == "verify_current" and not self.check_email(email):
            raise UserServiceError("Email is not registered.", status.HTTP_404_NOT_FOUND)

        expires_at = _utcnow() + timedelta(seconds=RESET_CODE_TTL_SECONDS)
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO email_verification_tokens (email, purpose, code, expires_at)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE code = VALUES(code), expires_at = VALUES(expires_at),
                        verification_token = NULL, verified_at = NULL
                    """,
                    (email, purpose, RESET_CODE, expires_at),
                )
                connection.commit()
        else:
            with self._lock:
                self._email_verifications[(email, purpose)] = {
                    "code": RESET_CODE,
                    "expires_at": expires_at,
                }
        return RESET_CODE_TTL_SECONDS

    def verify_email_verification_code(
        self,
        *,
        email: str,
        code: str,
        purpose: EmailVerificationPurpose,
    ) -> tuple[bool, Optional[str]]:
        email = _normalize_email(email)
        verification_token = secrets.token_urlsafe(32)
        now = _utcnow()
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT code, expires_at FROM email_verification_tokens
                    WHERE email = %s AND purpose = %s
                    """,
                    (email, purpose),
                )
                row = cursor.fetchone()
                if not row or row["code"] != code or row["expires_at"] < now:
                    return False, None
                cursor = connection.cursor()
                cursor.execute(
                    """
                    UPDATE email_verification_tokens
                    SET verification_token = %s, verified_at = %s
                    WHERE email = %s AND purpose = %s
                    """,
                    (verification_token, now, email, purpose),
                )
                connection.commit()
            return True, verification_token

        with self._lock:
            record = self._email_verifications.get((email, purpose))
            if not record or record["code"] != code or record["expires_at"] < now:
                return False, None
            record["verification_token"] = verification_token
            record["verified_at"] = now
            self._email_verification_tokens[verification_token] = {
                "email": email,
                "purpose": purpose,
                "expires_at": record["expires_at"],
            }
        return True, verification_token

    def _consume_email_verification_token(
        self,
        *,
        email: str,
        purpose: EmailVerificationPurpose,
        verification_token: str,
    ) -> None:
        email = _normalize_email(email)
        now = _utcnow()
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT expires_at FROM email_verification_tokens
                    WHERE email = %s AND purpose = %s
                      AND verification_token = %s AND verified_at IS NOT NULL
                    """,
                    (email, purpose, verification_token),
                )
                row = cursor.fetchone()
                if not row or row["expires_at"] < now:
                    raise UserServiceError("Invalid email verification token.", status.HTTP_400_BAD_REQUEST)
                cursor = connection.cursor()
                cursor.execute(
                    "DELETE FROM email_verification_tokens WHERE email = %s AND purpose = %s",
                    (email, purpose),
                )
                connection.commit()
            return

        with self._lock:
            record = self._email_verification_tokens.pop(verification_token, None)
            if (
                not record
                or record["email"] != email
                or record["purpose"] != purpose
                or record["expires_at"] < now
            ):
                raise UserServiceError("Invalid email verification token.", status.HTTP_400_BAD_REQUEST)
            self._email_verifications.pop((email, purpose), None)

    def check_email(self, email: str) -> bool:
        profile, _ = self._get_user_with_password(_normalize_email(email))
        return profile is not None

    def get_password_reset_method(self, email: str) -> tuple[bool, str]:
        profile, _ = self._get_user_with_password(_normalize_email(email))
        if not profile:
            return False, "email"
        use_totp = profile.totp_enabled and profile.totp_replaces_email_codes
        return True, "totp" if use_totp else "email"

    def send_reset_code(self, email: str) -> tuple[int, str]:
        email = _normalize_email(email)
        registered, verification_method = self.get_password_reset_method(email)
        if not registered:
            raise UserServiceError("Email is not registered.", status.HTTP_404_NOT_FOUND)
        if verification_method == "totp":
            return 0, "totp"
        expires_at = _utcnow() + timedelta(seconds=RESET_CODE_TTL_SECONDS)
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO password_reset_tokens (email, code, expires_at)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE code = VALUES(code), expires_at = VALUES(expires_at),
                        reset_token = NULL, verified_at = NULL
                    """,
                    (email, RESET_CODE, expires_at),
                )
                connection.commit()
        else:
            with self._lock:
                self._reset_by_email[email] = {"code": RESET_CODE, "expires_at": expires_at}
        return RESET_CODE_TTL_SECONDS, "email"

    def verify_reset_code(self, *, email: str, code: str) -> tuple[bool, Optional[str]]:
        email = _normalize_email(email)
        profile, _ = self._get_user_with_password(email)
        if not profile:
            return False, None
        self._check_rate_limit("password_reset_verify:email", email, limit=8)
        reset_token = secrets.token_urlsafe(32)
        now = _utcnow()
        if profile.totp_enabled and profile.totp_replaces_email_codes:
            if not self.verify_totp_code(profile.id, code):
                return False, None
            expires_at = now + timedelta(seconds=TOTP_CHALLENGE_TTL_SECONDS)
            if self._mysql_available:
                with self._connect() as connection:
                    cursor = connection.cursor()
                    cursor.execute(
                        """
                        INSERT INTO password_reset_tokens (email, code, expires_at, reset_token, verified_at)
                        VALUES (%s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE code = VALUES(code), expires_at = VALUES(expires_at),
                            reset_token = VALUES(reset_token), verified_at = VALUES(verified_at)
                        """,
                        (email, "totp", expires_at, reset_token, now),
                    )
                    connection.commit()
            else:
                with self._lock:
                    self._reset_by_email[email] = {
                        "code": "totp",
                        "expires_at": expires_at,
                        "reset_token": reset_token,
                        "verified_at": now,
                    }
                    self._reset_tokens[reset_token] = {"email": email, "expires_at": expires_at}
            return True, reset_token
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SELECT code, expires_at FROM password_reset_tokens WHERE email = %s", (email,))
                row = cursor.fetchone()
                if not row or row["code"] != code or row["expires_at"] < now:
                    return False, None
                cursor = connection.cursor()
                cursor.execute(
                    """
                    UPDATE password_reset_tokens
                    SET reset_token = %s, verified_at = %s
                    WHERE email = %s
                    """,
                    (reset_token, now, email),
                )
                connection.commit()
            return True, reset_token

        with self._lock:
            record = self._reset_by_email.get(email)
            if not record or record["code"] != code or record["expires_at"] < now:
                return False, None
            record["reset_token"] = reset_token
            record["verified_at"] = now
            self._reset_tokens[reset_token] = {"email": email, "expires_at": record["expires_at"]}
        return True, reset_token

    def reset_password(self, *, reset_token: str, new_password: str) -> None:
        password_hash = _hash_password(new_password)
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT email, expires_at FROM password_reset_tokens
                    WHERE reset_token = %s AND verified_at IS NOT NULL
                    """,
                    (reset_token,),
                )
                row = cursor.fetchone()
                if not row or row["expires_at"] < _utcnow():
                    raise UserServiceError("Invalid reset token.", status.HTTP_400_BAD_REQUEST)
                email = row["email"]
                cursor = connection.cursor()
                cursor.execute("UPDATE users SET password_hash = %s WHERE email = %s", (password_hash, email))
                cursor.execute("DELETE FROM password_reset_tokens WHERE email = %s", (email,))
                connection.commit()
            return

        with self._lock:
            record = self._reset_tokens.pop(reset_token, None)
            if not record or record["expires_at"] < _utcnow():
                raise UserServiceError("Invalid reset token.", status.HTTP_400_BAD_REQUEST)
            user_id = self._email_index[record["email"]]
            self._users[user_id]["password_hash"] = password_hash

    def get_preferences(self, user_id: str) -> UserPreferences:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SELECT * FROM user_preferences WHERE user_id = %s", (user_id,))
                row = cursor.fetchone()
                if not row:
                    cursor = connection.cursor()
                    self._ensure_preferences_mysql(cursor, user_id)
                    connection.commit()
                    return UserPreferences()
            return UserPreferences(
                theme=row["theme"],
                language=row["language"],
                search_retention_days=int(row["search_retention_days"]),
                chat_retention_days=int(row["chat_retention_days"]),
                import_platforms=_json_load(row["import_platforms"], {}),
            )
        return self._preferences.setdefault(user_id, UserPreferences())

    def update_preferences(self, user_id: str, patch: UserPreferencesUpdate) -> UserPreferences:
        current = self.get_preferences(user_id)
        payload = current.model_dump()
        payload.update(patch.model_dump(exclude_none=True))
        updated = UserPreferences.model_validate(payload)
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO user_preferences (
                        user_id, theme, language, search_retention_days,
                        chat_retention_days, import_platforms
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        theme = VALUES(theme),
                        language = VALUES(language),
                        search_retention_days = VALUES(search_retention_days),
                        chat_retention_days = VALUES(chat_retention_days),
                        import_platforms = VALUES(import_platforms)
                    """,
                    (
                        user_id,
                        updated.theme,
                        updated.language,
                        updated.search_retention_days,
                        updated.chat_retention_days,
                        _json_dump(updated.import_platforms),
                    ),
                )
                connection.commit()
        else:
            self._preferences[user_id] = updated
        return updated

    def get_import_platforms(self, user_id: str) -> dict[str, bool]:
        return self.get_preferences(user_id).import_platforms

    def update_import_platform(self, user_id: str, platform_key: str, enabled: bool) -> dict[str, bool]:
        prefs = self.get_preferences(user_id)
        platforms = dict(prefs.import_platforms)
        platforms[platform_key] = enabled
        return self.update_preferences(
            user_id,
            UserPreferencesUpdate(import_platforms=platforms),
        ).import_platforms

    def list_devices(self, user_id: str, current_token_hash: str) -> list[DeviceInfo]:
        now = _utcnow()
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT d.id, d.device_name, d.ip_address, d.login_time, d.token_hash
                    FROM user_devices d
                    JOIN auth_tokens t ON t.token_hash = d.token_hash
                    WHERE d.user_id = %s
                      AND d.revoked_at IS NULL
                      AND t.revoked_at IS NULL
                      AND (t.expires_at IS NULL OR t.expires_at > %s)
                    ORDER BY d.login_time DESC
                    """,
                    (user_id, now),
                )
                rows = cursor.fetchall()
            return [
                DeviceInfo(
                    id=row["id"],
                    device_name=row["device_name"],
                    ip_address=row["ip_address"],
                    login_time=row["login_time"],
                    is_current=row["token_hash"] == current_token_hash,
                )
                for row in rows
            ]

        return [
            DeviceInfo(
                id=device["id"],
                device_name=device["device_name"],
                ip_address=device["ip_address"],
                login_time=device["login_time"],
                is_current=device["token_hash"] == current_token_hash,
            )
            for device in self._devices.get(user_id, {}).values()
            if device.get("revoked_at") is None
            and (token := self._tokens.get(device["token_hash"])) is not None
            and token.get("revoked_at") is None
            and (
                token.get("expires_at") is None
                or token["expires_at"] > now
            )
        ]

    def revoke_device(
        self,
        user_id: str,
        device_id: str,
        current_token_hash: str,
        *,
        request: Optional[Request] = None,
    ) -> None:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    "SELECT token_hash FROM user_devices WHERE id = %s AND user_id = %s",
                    (device_id, user_id),
                )
                row = cursor.fetchone()
                if not row:
                    raise UserServiceError("Device not found.", status.HTTP_404_NOT_FOUND)
                if row["token_hash"] == current_token_hash:
                    raise UserServiceError("Cannot revoke current device.", status.HTTP_400_BAD_REQUEST)
                cursor = connection.cursor()
                cursor.execute("UPDATE user_devices SET revoked_at = %s WHERE id = %s", (_utcnow(), device_id))
                cursor.execute(
                    "UPDATE auth_tokens SET revoked_at = %s WHERE token_hash = %s",
                    (_utcnow(), row["token_hash"]),
                )
                connection.commit()
            self._record_audit_event(
                event_type="device_revoked",
                user_id=user_id,
                request=request,
                success=True,
                metadata={"device_id": device_id},
            )
            return

        with self._lock:
            device = self._devices.get(user_id, {}).get(device_id)
            if not device:
                raise UserServiceError("Device not found.", status.HTTP_404_NOT_FOUND)
            if device["token_hash"] == current_token_hash:
                raise UserServiceError("Cannot revoke current device.", status.HTTP_400_BAD_REQUEST)
            device["revoked_at"] = _utcnow()
            if device["token_hash"] in self._tokens:
                self._tokens[device["token_hash"]]["revoked_at"] = _utcnow()
        self._record_audit_event(
            event_type="device_revoked",
            user_id=user_id,
            request=request,
            success=True,
            metadata={"device_id": device_id},
        )

    def list_favorites(self, user_id: str) -> list[RoutePlan]:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT route_json FROM user_favorites
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()
            return [RoutePlan.model_validate(_json_load(row["route_json"], {})) for row in rows]

        entries = self._favorites.get(user_id, {}).values()
        ordered = sorted(entries, key=lambda item: item["created_at"], reverse=True)
        return [item["route"] for item in ordered]

    def add_favorite(self, user_id: str, route: RoutePlan) -> FavoriteCreateResponse:
        favorite_id = f"fav_{uuid4().hex}"
        created_at = _utcnow()
        if self._mysql_available:
            try:
                with self._connect() as connection:
                    cursor = connection.cursor()
                    cursor.execute(
                        """
                        INSERT INTO user_favorites (id, user_id, route_id, route_json, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            favorite_id,
                            user_id,
                            route.id,
                            _json_dump(route.model_dump(mode="json")),
                            created_at,
                        ),
                    )
                    connection.commit()
            except Exception as exc:
                raise UserServiceError("Route is already favorited.", status.HTTP_409_CONFLICT) from exc
            return FavoriteCreateResponse(id=favorite_id, created_at=created_at)

        with self._lock:
            user_favorites = self._favorites.setdefault(user_id, {})
            if route.id in user_favorites:
                raise UserServiceError("Route is already favorited.", status.HTTP_409_CONFLICT)
            user_favorites[route.id] = {"id": favorite_id, "route": route, "created_at": created_at}
        return FavoriteCreateResponse(id=favorite_id, created_at=created_at)

    def delete_favorite(self, user_id: str, route_id: str) -> None:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "DELETE FROM user_favorites WHERE user_id = %s AND route_id = %s",
                    (user_id, route_id),
                )
                connection.commit()
            return
        self._favorites.get(user_id, {}).pop(route_id, None)

    def save_ai_session(self, user_id: str, response: AISearchResponse, *, title: Optional[str] = None) -> None:
        title = (title or response.summary or "AI Search").strip()[:120] or "AI Search"
        last_preview = response.conversation[-1].content[:120] if response.conversation else ""
        now = _utcnow()
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO ai_search_sessions (
                        session_id, user_id, title, status, last_message_preview,
                        response_json, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        title = IF(title = 'AI Search', VALUES(title), title),
                        status = VALUES(status),
                        last_message_preview = VALUES(last_message_preview),
                        response_json = VALUES(response_json),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        response.session_id,
                        user_id,
                        title,
                        response.status.value,
                        last_preview,
                        "{}",
                        now,
                        now,
                    ),
                )
                connection.commit()
            return

        with self._lock:
            user_sessions = self._ai_sessions.setdefault(user_id, {})
            created_at = user_sessions.get(response.session_id, {}).get("created_at", now)
            existing_title = user_sessions.get(response.session_id, {}).get("title")
            user_sessions[response.session_id] = {
                "session_id": response.session_id,
                "title": existing_title or title,
                "status": response.status,
                "last_message_preview": last_preview,
                "response": response,
                "created_at": created_at,
                "updated_at": now,
            }

    def assert_ai_session_owner(self, user_id: str, session_id: str) -> None:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT 1 FROM ai_search_sessions WHERE session_id = %s AND user_id = %s",
                    (session_id, user_id),
                )
                if cursor.fetchone() is None:
                    raise UserServiceError("AI session not found.", status.HTTP_404_NOT_FOUND)
            return
        if session_id not in self._ai_sessions.get(user_id, {}):
            raise UserServiceError("AI session not found.", status.HTTP_404_NOT_FOUND)

    def check_ai_agent_quota(self, user_id: str) -> None:
        now = _utcnow()
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM ai_agent_usage WHERE user_id = %s AND created_at >= %s",
                    (user_id, now - timedelta(minutes=1)),
                )
                if int(cursor.fetchone()[0]) >= settings.ai_agent_minute_turn_limit:
                    raise UserServiceError("AI request limit reached. Please wait before trying again.", status.HTTP_429_TOO_MANY_REQUESTS)
                cursor.execute(
                    "SELECT COUNT(*) FROM ai_agent_usage WHERE user_id = %s AND created_at >= %s",
                    (user_id, now - timedelta(days=1)),
                )
                if int(cursor.fetchone()[0]) >= settings.ai_agent_daily_turn_limit:
                    raise UserServiceError("Daily AI request limit reached.", status.HTTP_429_TOO_MANY_REQUESTS)
                cursor.execute("INSERT INTO ai_agent_usage (user_id) VALUES (%s)", (user_id,))
                connection.commit()
            return
        self._check_rate_limit(
            "ai_agent_minute:user",
            user_id,
            limit=settings.ai_agent_minute_turn_limit,
            window_seconds=60,
        )

    def check_ai_session_capacity(self, user_id: str) -> None:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT COUNT(*) FROM ai_search_sessions WHERE user_id = %s", (user_id,))
                if int(cursor.fetchone()[0]) >= settings.ai_agent_max_sessions:
                    raise UserServiceError("AI session limit reached.", status.HTTP_409_CONFLICT)
            return
        if len(self._ai_sessions.get(user_id, {})) >= settings.ai_agent_max_sessions:
            raise UserServiceError("AI session limit reached.", status.HTTP_409_CONFLICT)

    def reserve_ai_request(self, user_id: str, session_id: str, request_id: str) -> bool:
        if self._mysql_available:
            try:
                with self._connect() as connection:
                    cursor = connection.cursor()
                    cursor.execute(
                        "INSERT INTO ai_agent_requests (request_id, user_id, session_id) VALUES (%s, %s, %s)",
                        (request_id, user_id, session_id),
                    )
                    connection.commit()
                return True
            except Exception:
                return False
        key = f"ai_request:{request_id}"
        with self._lock:
            if key in self._rate_limits:
                return False
            self._rate_limits[key] = [_utcnow()]
        return True

    def acquire_ai_session_run(self, user_id: str, session_id: str, run_id: str) -> None:
        self.assert_ai_session_owner(user_id, session_id)
        if not self._mysql_available:
            return
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE ai_search_sessions
                SET active_run_id = %s, active_run_started_at = %s
                WHERE session_id = %s AND user_id = %s
                  AND (active_run_id IS NULL OR active_run_started_at < %s)
                """,
                (run_id, _utcnow(), session_id, user_id, _utcnow() - timedelta(minutes=2)),
            )
            if cursor.rowcount == 0:
                raise UserServiceError("This AI session already has a request in progress.", status.HTTP_409_CONFLICT)
            connection.commit()

    def release_ai_session_run(self, user_id: str, session_id: str, run_id: str) -> None:
        if not self._mysql_available:
            return
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE ai_search_sessions
                SET active_run_id = NULL, active_run_started_at = NULL
                WHERE session_id = %s AND user_id = %s AND active_run_id = %s
                """,
                (session_id, user_id, run_id),
            )
            connection.commit()

    def queue_ai_checkpoint_deletion(self, user_id: str, session_id: str, error: str = "") -> None:
        if not self._mysql_available:
            return
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO ai_checkpoint_deletions (session_id, user_id, last_error)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE last_error = VALUES(last_error), completed_at = NULL
                """,
                (session_id, user_id, error[:255]),
            )
            connection.commit()

    def list_user_ai_session_ids(self, user_id: str) -> list[str]:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute("SELECT session_id FROM ai_search_sessions WHERE user_id = %s", (user_id,))
                return [str(row[0]) for row in cursor.fetchall()]
        return list(self._ai_sessions.get(user_id, {}).keys())

    def list_expired_ai_session_ids(self, user_id: str) -> list[str]:
        if not self._mysql_available:
            return []
        with self._connect() as connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT sessions.session_id, sessions.updated_at, preferences.chat_retention_days
                FROM ai_search_sessions AS sessions
                JOIN user_preferences AS preferences ON preferences.user_id = sessions.user_id
                WHERE sessions.user_id = %s AND preferences.chat_retention_days >= 0
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
        now = _utcnow()
        return [
            str(row["session_id"])
            for row in rows
            if row["updated_at"] <= now - timedelta(days=int(row["chat_retention_days"]))
        ]

    def list_pending_ai_checkpoint_deletions(self, user_id: str) -> list[str]:
        if not self._mysql_available:
            return []
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT session_id FROM ai_checkpoint_deletions
                WHERE user_id = %s AND completed_at IS NULL
                ORDER BY created_at
                LIMIT 20
                """,
                (user_id,),
            )
            return [str(row[0]) for row in cursor.fetchall()]

    def complete_ai_checkpoint_deletion(self, session_id: str) -> None:
        if not self._mysql_available:
            return
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE ai_checkpoint_deletions SET completed_at = %s, last_error = NULL WHERE session_id = %s",
                (_utcnow(), session_id),
            )
            connection.commit()

    def list_ai_sessions(self, user_id: str) -> list[AISessionSummary]:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT session_id, title, status, last_message_preview, created_at, updated_at
                    FROM ai_search_sessions
                    WHERE user_id = %s
                    ORDER BY updated_at DESC
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()
            return [self._ai_summary_from_row(row) for row in rows]

        rows = sorted(
            self._ai_sessions.get(user_id, {}).values(),
            key=lambda item: item["updated_at"],
            reverse=True,
        )
        return [
            AISessionSummary(
                session_id=row["session_id"],
                title=row["title"],
                status=row["status"],
                last_message_preview=row["last_message_preview"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def rename_ai_session(self, user_id: str, session_id: str, title: str) -> AISessionSummary:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    UPDATE ai_search_sessions
                    SET title = %s, updated_at = %s
                    WHERE user_id = %s AND session_id = %s
                    """,
                    (title, _utcnow(), user_id, session_id),
                )
                if cursor.rowcount == 0:
                    raise UserServiceError("AI session not found.", status.HTTP_404_NOT_FOUND)
                connection.commit()
            return next(item for item in self.list_ai_sessions(user_id) if item.session_id == session_id)

        session = self._ai_sessions.get(user_id, {}).get(session_id)
        if not session:
            raise UserServiceError("AI session not found.", status.HTTP_404_NOT_FOUND)
        session["title"] = title
        session["updated_at"] = _utcnow()
        return next(item for item in self.list_ai_sessions(user_id) if item.session_id == session_id)

    def delete_ai_session(self, user_id: str, session_id: str) -> None:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "DELETE FROM ai_search_sessions WHERE user_id = %s AND session_id = %s",
                    (user_id, session_id),
                )
                connection.commit()
            return
        self._ai_sessions.get(user_id, {}).pop(session_id, None)

    def create_booking(self, user_id: str, route_id: str, legs: list[dict]) -> BookingCreateResponse:
        booking_id = f"booking_{uuid4().hex[:16]}"
        status_text = "created"
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO bookings (booking_id, user_id, route_id, legs_json, status)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (booking_id, user_id, route_id, _json_dump(legs), status_text),
                )
                connection.commit()
        else:
            self._bookings[booking_id] = {
                "booking_id": booking_id,
                "user_id": user_id,
                "route_id": route_id,
                "legs": legs,
                "status": status_text,
            }
        return BookingCreateResponse(booking_id=booking_id, status=status_text, redirect_url=None)

    def _issue_token(
        self,
        profile: UserProfile,
        *,
        session_duration: SessionDuration,
        request: Optional[Request],
    ) -> AuthTokenResponse:
        token = secrets.token_urlsafe(32)
        token_hash = _token_hash(token)
        device_id = f"device_{uuid4().hex}"
        device_name = request.headers.get("user-agent", "Unknown device")[:255] if request else "Unknown device"
        ip_address = request.client.host if request and request.client else "unknown"
        now = _utcnow()
        delta = SESSION_DURATION_DELTAS[session_duration]
        expires_at = now + delta if delta is not None else None

        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO user_devices (id, user_id, token_hash, device_name, ip_address, login_time)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (device_id, profile.id, token_hash, device_name, ip_address, now),
                )
                cursor.execute(
                    """
                    INSERT INTO auth_tokens (token_hash, user_id, device_id, created_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (token_hash, profile.id, device_id, now, expires_at),
                )
                connection.commit()
        else:
            with self._lock:
                self._tokens[token_hash] = {
                    "user_id": profile.id,
                    "device_id": device_id,
                    "created_at": now,
                    "expires_at": expires_at,
                    "revoked_at": None,
                }
                self._devices.setdefault(profile.id, {})[device_id] = {
                    "id": device_id,
                    "user_id": profile.id,
                    "token_hash": token_hash,
                    "device_name": device_name,
                    "ip_address": ip_address,
                    "login_time": now,
                    "revoked_at": None,
                }

        return AuthTokenResponse(
            user=profile,
            access_token=token,
            token_type="bearer",
            expires_at=expires_at,
            session_duration=session_duration,
        )

    def _get_user_with_password(self, email: str) -> tuple[Optional[UserProfile], Optional[str]]:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    "SELECT id, username, email, password_hash, email_verified, totp_enabled, totp_replaces_email_codes, nickname, avatar_url, created_at FROM users WHERE email = %s",
                    (email,),
                )
                row = cursor.fetchone()
            if not row:
                return None, None
            return self._profile_from_row(row), row["password_hash"]

        user_id = self._email_index.get(email)
        if not user_id:
            return None, None
        record = self._users[user_id]
        return record["profile"], record["password_hash"]

    def _get_profile_by_id(self, user_id: str) -> Optional[UserProfile]:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    "SELECT id, username, email, email_verified, totp_enabled, totp_replaces_email_codes, nickname, avatar_url, created_at FROM users WHERE id = %s",
                    (user_id,),
                )
                row = cursor.fetchone()
            return self._profile_from_row(row) if row else None
        record = self._users.get(user_id)
        return record["profile"] if record else None

    def _set_password(self, user_id: str, password_hash: str) -> None:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))
                connection.commit()
            return
        self._users[user_id]["password_hash"] = password_hash

    @staticmethod
    def _profile_from_row(row: dict) -> UserProfile:
        return UserProfile(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            email_verified=bool(row.get("email_verified", True)),
            totp_enabled=bool(row.get("totp_enabled", False)),
            totp_replaces_email_codes=bool(row.get("totp_replaces_email_codes", False)),
            nickname=row.get("nickname"),
            avatar_url=row.get("avatar_url"),
            created_at=row["created_at"],
        )

    @staticmethod
    def _ai_summary_from_row(row: dict) -> AISessionSummary:
        return AISessionSummary(
            session_id=row["session_id"],
            title=row["title"],
            status=AISearchSessionStatus(row["status"]),
            last_message_preview=row["last_message_preview"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _ensure_preferences_mysql(cursor, user_id: str) -> None:
        cursor.execute(
            """
            INSERT IGNORE INTO user_preferences (
                user_id, theme, language, search_retention_days,
                chat_retention_days, import_platforms
            )
            VALUES (%s, 'light', 'zh', 30, 30, '{}')
            """,
            (user_id,),
        )


@lru_cache
def get_user_service() -> UserService:
    return UserService()


def reset_user_service_cache() -> None:
    get_user_service.cache_clear()


def _unauthorized(detail: str = "Authentication required.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[AuthenticatedUser]:
    if credentials is not None:
        if not _bearer_auth_enabled():
            return None
        try:
            return get_user_service().authenticate_token(credentials.credentials)
        except UserServiceError:
            return None
    cookie_token = request.cookies.get(settings.auth_cookie_name)
    if not cookie_token:
        return None
    try:
        return get_user_service().authenticate_token(cookie_token)
    except UserServiceError:
        return None


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> AuthenticatedUser:
    if credentials is not None:
        if not _bearer_auth_enabled():
            raise _unauthorized("Bearer authentication is disabled.")
        try:
            return get_user_service().authenticate_token(credentials.credentials)
        except UserServiceError as exc:
            raise _unauthorized(str(exc)) from exc
    cookie_token = request.cookies.get(settings.auth_cookie_name)
    if not cookie_token:
        raise _unauthorized()
    try:
        return get_user_service().authenticate_token(cookie_token)
    except UserServiceError as exc:
        raise _unauthorized(str(exc)) from exc


async def require_csrf(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> None:
    if request.method.upper() in SAFE_METHODS:
        return
    if credentials is not None and _bearer_auth_enabled():
        return
    session_token = request.cookies.get(settings.auth_cookie_name)
    if not session_token:
        return
    csrf_cookie = request.cookies.get(settings.csrf_cookie_name)
    csrf_header = request.headers.get(settings.csrf_header_name)
    if not csrf_cookie or not csrf_header:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token is required.")
    if not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token mismatch.")
    if not _verify_csrf_token(session_token=session_token, csrf_token=csrf_header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token.")


async def bearer_credentials(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[HTTPAuthorizationCredentials]:
    return credentials
