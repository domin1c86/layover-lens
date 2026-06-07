# Layover Lens API 接口清单

本文档按当前 FastAPI 路由整理。业务 API 统一前缀为 `/api/v1`；根路径 `/`、`/health`、`/docs`、`/redoc` 不带该前缀。

## 通用约定

- 请求/响应：默认 `application/json`，头像上传和读取除外。
- Web 登录态：后端通过 `HttpOnly` Session Cookie 识别用户。
- CSRF：登录态下的状态修改接口需要 CSRF Header；前端 `apiClient` 会自动从 CSRF Cookie 读取并添加。
- 兼容认证：开发环境可临时支持 `Authorization: Bearer <token>`；生产环境可关闭 bearer 兼容。
- AI SSE：流式接口返回 `text/event-stream`，事件包括 `status`、`assistant_delta`、`tool_result`、`search_result`、`done`、`error`。
- Mock/估算提示：路线搜索当前返回路线策略估算，不代表实时票价、实时余票或可购买班次。

## 基础接口

| Method | Path | 认证 | 说明 |
| --- | --- | --- | --- |
| `GET` | `/` | 否 | API 欢迎信息，返回 docs 和 health 入口。 |
| `GET` | `/health` | 否 | 服务状态、数据源、C++ planner、AI、POI、存储保护等能力摘要。 |
| `GET` | `/docs` | 否 | Swagger UI。 |
| `GET` | `/redoc` | 否 | ReDoc 文档。 |

## 城市与路线搜索

| Method | Path | 认证 | 请求 | 响应 | 前端调用 |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/cities?keyword=...` | 否 | query: `keyword?: string` | `CityListResponse` | `cityApi.getCities()` |
| `POST` | `/api/v1/search` | 否 | `SearchRequest` | `SearchResponse` | `searchApi.search()` |
| `POST` | `/api/v1/search/feedback` | 可选 | `RouteFeedbackCreateRequest` | `RouteFeedbackResponse` | `searchApi.submitRouteFeedback()` |
| `PUT` | `/api/v1/search/feedback/{feedback_id}/annotation` | 是 | `RouteFeedbackAnnotationRequest` | `RouteFeedbackAnnotationResponse` | 人工标注/训练数据维护 |
| `GET` | `/api/v1/search/feedback/annotated` | 是 | 无 | `{ samples: object[], total: number }` | 训练样本导出 |

### `SearchRequest`

```ts
interface SearchRequest {
  from_city: string
  to_city: string
  travel_date: string
  optimization_target: 'price' | 'time' | 'transfer' | 'balanced'
  max_transfers?: number
  min_transfers?: number
  preferred_transport_types?: Array<'flight' | 'train'>
  max_price?: number
  max_total_duration_minutes?: number
  excluded_cities?: string[]
  required_transfer_cities?: string[]
  departure_time_range?: { start: string; end: string }
  arrival_time_range?: { start: string; end: string }
  allow_overnight?: boolean
}
```

兼容旧字段：`date` -> `travel_date`，`optimize` -> `optimization_target`，`filters.max_transfer` -> `max_transfers`，`filters.transport_types` -> `preferred_transport_types`。

### `SearchResponse`

```ts
interface SearchResponse {
  search_id: string
  result_mode: 'strategy' | 'legacy_detail'
  recommendations: RouteRecommendation[]
  routes: RoutePlan[]
  total_count: number
  total: number
  strategy_notice?: string
  data_mode: 'mock' | 'historical'
  data_notice?: string
  mock_source_date?: string
  route_dataset_mode?: string
  route_dataset_version?: string
  route_model_version?: string
}
```

当前默认 `result_mode = "strategy"`，前端主展示 `recommendations`。

### `RouteFeedbackCreateRequest`

```ts
interface RouteFeedbackCreateRequest {
  search_id: string
  recommendation_id: string
  anonymous_session_id?: string
  action?: 'shown' | 'selected' | 'favorited' | 'ignored' | 'negative'
  source: 'search' | 'ai'
  feedback_context: 'route_card' | 'ai_experience'
  ratings?: {
    overall: number
    route_reasonable: number
    cost_trustworthy: number
    transfer_clear: number
  }
  selected_recommendation_ids?: string[]
  clicked_provider?: '12306' | 'ctrip' | 'fliggy' | 'qunar'
  clicked_segment_index?: number
  comment?: string
  search_request?: object
  recommendation?: object
  model_version?: string
  dataset_version?: string
}
```

匿名评价必须提供 `anonymous_session_id`；登录用户会自动绑定 `user_id`。

## AI 搜索与会话

| Method | Path | 认证 | 请求 | 响应 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/search/ai/sessions` | 是 | `AISearchSessionCreateRequest` | `AISearchResponse` | 创建 AI 会话，非流式。 |
| `POST` | `/api/v1/search/ai/sessions/stream` | 是 + CSRF | `AISearchSessionCreateRequest` | SSE | 创建 AI 会话，流式返回。 |
| `GET` | `/api/v1/search/ai/sessions` | 是 | 无 | `AISessionListResponse` | 当前用户 AI 会话摘要列表。 |
| `GET` | `/api/v1/search/ai/sessions/{session_id}` | 是 | 无 | `AISearchResponse` | 读取单个会话详情，校验 owner。 |
| `POST` | `/api/v1/search/ai/sessions/{session_id}/messages` | 是 | `AISearchSessionTurnRequest` | `AISearchResponse` | 追加用户消息，非流式。 |
| `POST` | `/api/v1/search/ai/sessions/{session_id}/messages/stream` | 是 + CSRF | `AISearchSessionTurnRequest` | SSE | 追加用户消息，流式返回。 |
| `POST` | `/api/v1/search/ai/sessions/{session_id}/confirm` | 是 | `AISearchSessionConfirmRequest` | `AISearchResponse` | 确认或拒绝执行搜索，非流式。 |
| `POST` | `/api/v1/search/ai/sessions/{session_id}/confirm/stream` | 是 + CSRF | `AISearchSessionConfirmRequest` | SSE | 确认或拒绝执行搜索，流式返回。 |
| `PUT` | `/api/v1/search/ai/sessions/{session_id}` | 是 + CSRF | `AISessionUpdateRequest` | `AISessionSummary` | 重命名会话。 |
| `DELETE` | `/api/v1/search/ai/sessions/{session_id}` | 是 + CSRF | 无 | `SuccessResponse` | 删除会话和 checkpoint。 |
| `POST` | `/api/v1/search/ai/summarize` | 是 + CSRF | `SummarizeRequest` | `SummarizeResponse` | 规则生成会话标题。 |

### AI 请求模型

```ts
interface AISearchSessionCreateRequest {
  message: string
  language?: 'zh' | 'en'
  request_id?: string
}

interface AISearchSessionTurnRequest {
  message: string
  language?: 'zh' | 'en'
  request_id?: string
}

interface AISearchSessionConfirmRequest {
  confirmed: boolean
  language?: 'zh' | 'en'
  request_id?: string
}
```

`request_id` 用于幂等保护。

## 认证接口

| Method | Path | 认证 | 请求 | 响应 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/auth/register` | 否 | `AuthRegisterRequest` | `AuthTokenResponse` | 注册，设置 Session/CSRF Cookie。 |
| `POST` | `/api/v1/auth/login` | 否 | `AuthLoginRequest` | `AuthLoginResponse` | 登录；启用 TOTP 时返回 challenge。 |
| `POST` | `/api/v1/auth/login/totp` | 否 | `AuthTotpVerifyRequest` | `AuthTokenResponse` | 完成 TOTP 登录。 |
| `POST` | `/api/v1/auth/logout` | 是 + CSRF | 无 | `SuccessResponse` | 退出并撤销当前 token。 |
| `POST` | `/api/v1/auth/email-verification/send` | 否 | `EmailVerificationSendRequest` | `EmailVerificationSendResponse` | 发送邮箱验证码；当前内测码为 `000000`。 |
| `POST` | `/api/v1/auth/email-verification/verify` | 否 | `EmailVerificationVerifyRequest` | `EmailVerificationVerifyResponse` | 校验邮箱验证码并返回 verification token。 |
| `POST` | `/api/v1/auth/forgot-password/check-email` | 否 | `ForgotPasswordCheckEmailRequest` | `ForgotPasswordCheckEmailResponse` | 查询邮箱是否注册及验证方式。 |
| `POST` | `/api/v1/auth/forgot-password/send-code` | 否 | `ForgotPasswordSendCodeRequest` | `ForgotPasswordSendCodeResponse` | 发送重置密码验证码或触发 2FA 流程。 |
| `POST` | `/api/v1/auth/forgot-password/verify-code` | 否 | `ForgotPasswordVerifyCodeRequest` | `ForgotPasswordVerifyCodeResponse` | 校验重置密码验证码并返回 reset token。 |
| `POST` | `/api/v1/auth/forgot-password/reset` | 否 | `ForgotPasswordResetRequest` | `SuccessResponse` | 使用 reset token 设置新密码。 |

### 登录保持时长

`session_duration` 可选值：

```text
day | week | month | half_year | year | forever
```

默认 `day`，即 24 小时。`forever` 表示不主动按时间过期，但退出登录或设备撤销仍会失效。

## 用户与账户设置

| Method | Path | 认证 | 请求 | 响应 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/user/profile` | 是 | 无 | `UserProfile` | 当前用户资料。 |
| `PUT` | `/api/v1/user/profile` | 是 + CSRF | `{ nickname: string }` | `UserProfile` | 修改昵称。 |
| `DELETE` | `/api/v1/user/account` | 是 + CSRF | 无 | `SuccessResponse` | 注销账号并删除关联数据。 |
| `POST` | `/api/v1/user/avatar` | 是 + CSRF | 图片 body 或 form-data | `AvatarResponse` | 上传头像到后端。 |
| `PUT` | `/api/v1/user/avatar/preset` | 是 + CSRF | `AvatarPresetUpdateRequest` | `UserProfile` | 保存预设头像引用，如 `material:m1`。 |
| `GET` | `/api/v1/user/avatar/{user_id}` | 否 | 无 | 图片二进制 | 读取用户上传头像。 |
| `PUT` | `/api/v1/user/email` | 是 + CSRF | `UserEmailUpdateRequest` | `UserProfile` | 修改邮箱，需旧邮箱确认和新邮箱 verification token。 |
| `POST` | `/api/v1/user/email/verify` | 是 + CSRF | `UserEmailVerifyRequest` | `UserProfile` | 验证当前邮箱。 |
| `POST` | `/api/v1/user/password/check` | 是 + CSRF | `UserPasswordCheckRequest` | `UserPasswordCheckResponse` | 校验当前密码。 |
| `PUT` | `/api/v1/user/password` | 是 + CSRF | `UserPasswordUpdateRequest` | `SuccessResponse` | 修改密码，并撤销其他设备 token。 |
| `POST` | `/api/v1/user/totp/setup` | 是 + CSRF | `TotpSetupRequest` | `TotpSetupResponse` | 创建认证器 2FA 绑定信息和二维码 URI。 |
| `POST` | `/api/v1/user/totp/enable` | 是 + CSRF | `TotpEnableRequest` | `UserProfile` | 校验动态码并启用 TOTP。 |
| `POST` | `/api/v1/user/totp/disable` | 是 + CSRF | `TotpDisableRequest` | `UserProfile` | 用密码和动态码关闭 TOTP。 |
| `PUT` | `/api/v1/user/totp/email-code-replacement` | 是 + CSRF | `TotpEmailCodeReplacementUpdateRequest` | `UserProfile` | 控制是否用 TOTP 替代邮件验证码。 |
| `PUT` | `/api/v1/user/session-duration` | 是 + CSRF | `SessionDurationUpdateRequest` | `SessionDurationUpdateResponse` | 直接更新当前登录 token 的保持时长。 |

## 偏好、设备、收藏与导入设置

| Method | Path | 认证 | 请求 | 响应 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `GET` | `/api/v1/user/preferences` | 是 | 无 | `UserPreferences` | 主题、语言、历史保留等偏好。 |
| `PUT` | `/api/v1/user/preferences` | 是 + CSRF | `Partial<UserPreferences>` | `UserPreferences` | 更新偏好。 |
| `GET` | `/api/v1/user/import-platforms` | 是 | 无 | `ImportPlatformsResponse` | 读取导入平台开关。 |
| `PUT` | `/api/v1/user/import-platforms` | 是 + CSRF | `ImportPlatformUpdateRequest` | `ImportPlatformsResponse` | 更新单个平台开关。 |
| `GET` | `/api/v1/user/devices` | 是 | 无 | `DeviceListResponse` | 登录设备列表，包含平台、IP、最后使用时间。 |
| `DELETE` | `/api/v1/user/devices/{device_id}` | 是 + CSRF | 无 | `SuccessResponse` | 下线指定设备。 |
| `GET` | `/api/v1/user/favorites` | 是 | 无 | `FavoriteListResponse` | 云端收藏列表。 |
| `POST` | `/api/v1/user/favorites` | 是 + CSRF | `FavoriteCreateRequest` | `FavoriteCreateResponse` | 保存收藏。 |
| `DELETE` | `/api/v1/user/favorites/{route_id}` | 是 + CSRF | 无 | `SuccessResponse` | 删除收藏。 |

当前前端收藏仍以本地体验为主；后端云端收藏接口保留用于后续同步。

## 预订接口

| Method | Path | 认证 | 请求 | 响应 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/bookings` | 是 + CSRF | `BookingCreateRequest` | `BookingCreateResponse` | 创建本地预订记录；当前不接真实票务供应商。 |

## 主要响应模型摘要

### `RouteRecommendation`

```ts
interface RouteRecommendation {
  id: string
  city_path: string[]
  city_path_en: string[]
  transfer_cities: string[]
  transfer_cities_en: string[]
  segments: RecommendationSegment[]
  estimated_total_price: number
  estimated_total_duration_minutes: number
  estimated_price_level: 'low' | 'medium' | 'high'
  estimated_duration_level: 'short' | 'medium' | 'long'
  transfer_count: number
  score: number
  confidence: number
  reasons: string[]
  warnings: string[]
  data_sources: string[]
}
```

### `RecommendationSegment`

```ts
interface RecommendationSegment {
  from_city: string
  to_city: string
  recommended_transport_type: 'flight' | 'train'
  available_transport_types: Array<'flight' | 'train'>
  estimated_price: number
  estimated_duration_minutes: number
  estimated_price_level: 'low' | 'medium' | 'high'
  estimated_duration_level: 'short' | 'medium' | 'long'
  service_frequency_level: 'low' | 'medium' | 'high'
  availability: SegmentAvailability
  data_source: string
}
```

### `UserProfile`

```ts
interface UserProfile {
  id: string
  username: string
  email: string
  email_verified: boolean
  nickname?: string | null
  avatar_url?: string | null
  totp_enabled: boolean
  totp_replaces_email_codes: boolean
  created_at: string
}
```

## 状态码约定

| 状态码 | 说明 |
| --- | --- |
| `200` | 成功 |
| `400` | 请求语义错误，如匿名反馈缺少匿名 session id |
| `401` | 未登录或 token 无效 |
| `403` | CSRF 缺失/不匹配，或权限不足 |
| `404` | 城市、会话、反馈等资源不存在 |
| `409` | 会话容量、运行锁、限流等冲突 |
| `422` | Pydantic 请求体验证失败 |
| `503` | AI 存储保护或外部能力暂不可用 |

## 前端 API 封装位置

- `frontend/src/services/api.ts`
  - `authApi`
  - `searchApi`
  - `cityApi`
  - `aiSearchApi`
- `frontend/src/types/index.ts`
  - 与后端 Pydantic schema 对应的 TypeScript 类型。

接口契约变更时，需要同步更新后端 `backend/app/schemas.py`、前端类型和相关测试。
