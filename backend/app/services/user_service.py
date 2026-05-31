from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from threading import Lock
from typing import Optional
from urllib.parse import unquote, urlparse
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.schemas import (
    AISearchResponse,
    AISearchSessionStatus,
    AISessionSummary,
    AuthTokenResponse,
    BookingCreateResponse,
    DeviceInfo,
    FavoriteCreateResponse,
    RoutePlan,
    SessionDuration,
    UserPreferences,
    UserPreferencesUpdate,
    UserProfile,
)


RESET_CODE = "000000"
RESET_CODE_TTL_SECONDS = 60
PASSWORD_ITERATIONS = 120_000
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


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
        self._avatars: dict[str, tuple[str, bytes]] = {}
        self._ai_sessions: dict[str, dict[str, dict]] = {}
        self._bookings: dict[str, dict] = {}

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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
        ]
        try:
            cursor = connection.cursor()
            for statement in statements:
                cursor.execute(statement)
            self._ensure_mysql_column(cursor, "auth_tokens", "expires_at", "TIMESTAMP NULL AFTER created_at")
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

    def register(
        self,
        *,
        username: str,
        email: str,
        password: str,
        session_duration: SessionDuration = "day",
        request: Optional[Request] = None,
    ) -> AuthTokenResponse:
        email = _normalize_email(email)
        user_id = f"user_{uuid4().hex}"
        created_at = _utcnow()
        profile = UserProfile(
            id=user_id,
            username=username.strip(),
            email=email,
            nickname=None,
            avatar_url=None,
            created_at=created_at,
        )
        password_hash = _hash_password(password)

        if self._mysql_available:
            try:
                with self._connect() as connection:
                    cursor = connection.cursor()
                    cursor.execute(
                        """
                        INSERT INTO users (id, username, email, password_hash, created_at)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (profile.id, profile.username, profile.email, password_hash, created_at),
                    )
                    self._ensure_preferences_mysql(cursor, profile.id)
                    connection.commit()
            except Exception as exc:
                raise UserServiceError("Email is already registered.", status.HTTP_409_CONFLICT) from exc
        else:
            with self._lock:
                if email in self._email_index:
                    raise UserServiceError("Email is already registered.", status.HTTP_409_CONFLICT)
                self._users[user_id] = {
                    "profile": profile,
                    "password_hash": password_hash,
                }
                self._email_index[email] = user_id
                self._preferences[user_id] = UserPreferences()

        return self._issue_token(profile, session_duration=session_duration, request=request)

    def login(
        self,
        *,
        email: str,
        password: str,
        session_duration: SessionDuration = "day",
        request: Optional[Request] = None,
    ) -> AuthTokenResponse:
        profile, password_hash = self._get_user_with_password(_normalize_email(email))
        if profile is None or not _verify_password(password, password_hash or ""):
            raise UserServiceError("Invalid email or password.", status.HTTP_401_UNAUTHORIZED)
        return self._issue_token(profile, session_duration=session_duration, request=request)

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

    def authenticate_token(self, token: str) -> AuthenticatedUser:
        token_hash = _token_hash(token)
        now = _utcnow()
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT u.id, u.username, u.email, u.nickname, u.avatar_url, u.created_at
                    FROM auth_tokens t
                    JOIN users u ON u.id = t.user_id
                    WHERE t.token_hash = %s
                      AND t.revoked_at IS NULL
                      AND (t.expires_at IS NULL OR t.expires_at > %s)
                    """,
                    (token_hash, now),
                )
                row = cursor.fetchone()
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

    def update_email(self, user_id: str, *, new_email: str, code: Optional[str]) -> UserProfile:
        if code is not None and code != RESET_CODE:
            raise UserServiceError("Invalid verification code.", status.HTTP_400_BAD_REQUEST)
        email = _normalize_email(new_email)
        if self._mysql_available:
            try:
                with self._connect() as connection:
                    cursor = connection.cursor()
                    cursor.execute("UPDATE users SET email = %s WHERE id = %s", (email, user_id))
                    connection.commit()
            except Exception as exc:
                raise UserServiceError("Email is already registered.", status.HTTP_409_CONFLICT) from exc
            return self.get_profile(user_id)

        with self._lock:
            if email in self._email_index and self._email_index[email] != user_id:
                raise UserServiceError("Email is already registered.", status.HTTP_409_CONFLICT)
            profile = self._users[user_id]["profile"]
            self._email_index.pop(profile.email, None)
            self._email_index[email] = user_id
            self._users[user_id]["profile"] = profile.model_copy(update={"email": email})
            return self._users[user_id]["profile"]

    def update_password(self, user_id: str, *, current_password: str, new_password: str) -> None:
        profile = self.get_profile(user_id)
        _, current_hash = self._get_user_with_password(profile.email)
        if not _verify_password(current_password, current_hash or ""):
            raise UserServiceError("Current password is incorrect.", status.HTTP_400_BAD_REQUEST)
        self._set_password(user_id, _hash_password(new_password))

    def check_email(self, email: str) -> bool:
        profile, _ = self._get_user_with_password(_normalize_email(email))
        return profile is not None

    def send_reset_code(self, email: str) -> int:
        email = _normalize_email(email)
        if not self.check_email(email):
            raise UserServiceError("Email is not registered.", status.HTTP_404_NOT_FOUND)
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
        return RESET_CODE_TTL_SECONDS

    def verify_reset_code(self, *, email: str, code: str) -> tuple[bool, Optional[str]]:
        email = _normalize_email(email)
        reset_token = secrets.token_urlsafe(32)
        now = _utcnow()
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
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT id, device_name, ip_address, login_time, token_hash
                    FROM user_devices
                    WHERE user_id = %s AND revoked_at IS NULL
                    ORDER BY login_time DESC
                    """,
                    (user_id,),
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
        ]

    def revoke_device(self, user_id: str, device_id: str, current_token_hash: str) -> None:
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
        payload = response.model_dump(mode="json")
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
                        _json_dump(payload),
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
                    "SELECT id, username, email, password_hash, nickname, avatar_url, created_at FROM users WHERE email = %s",
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
                    "SELECT id, username, email, nickname, avatar_url, created_at FROM users WHERE id = %s",
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
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[AuthenticatedUser]:
    if credentials is None:
        return None
    try:
        return get_user_service().authenticate_token(credentials.credentials)
    except UserServiceError:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> AuthenticatedUser:
    if credentials is None:
        raise _unauthorized()
    try:
        return get_user_service().authenticate_token(credentials.credentials)
    except UserServiceError as exc:
        raise _unauthorized(str(exc)) from exc


async def bearer_credentials(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[HTTPAuthorizationCredentials]:
    return credentials
