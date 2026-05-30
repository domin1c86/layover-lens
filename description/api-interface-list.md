# Layover Lens API 接口清单

统一业务前缀：`/api/v1`  
请求/响应格式：`application/json`，头像上传/读取除外  
认证方式：`Authorization: Bearer <token>`

## 基础接口

### GET `/`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端未调用；浏览器/运维健康确认可直接访问 |
| 路径 | `GET /` |
| 用途 | 返回 API 欢迎信息、文档入口和健康检查入口 |
| 请求体 | 无 |
| 响应体 | `{ message: string, docs: string, health: string }` |
| 认证 | 否 |

### GET `/health`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | Docker healthcheck；前端未直接调用 |
| 路径 | `GET /health` |
| 用途 | 返回服务状态、数据源、planner backend、AI backend |
| 请求体 | 无 |
| 响应体 | `{ status: string, data_source: string, planner_backend: string, ai_search_backend: string }` |
| 认证 | 否 |

## 城市与路线搜索

### GET `/api/v1/cities`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | `frontend/src/pages/HomePage.tsx` -> `cityApi.getCities()`；供 SearchBar 的城市选择器使用 |
| 路径 | `GET /api/v1/cities?keyword=...` |
| 用途 | 获取城市列表，可按城市中文名、英文名或代码过滤 |
| 请求体 | 无；查询参数：`keyword?: string` |
| 响应体 | `{ cities: City[] }` |
| 认证 | 否 |

### POST `/api/v1/search`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | `frontend/src/pages/HomePage.tsx` -> `searchApi.search(request)`；结果由 `SearchTab/ResultList` 渲染 |
| 路径 | `POST /api/v1/search` |
| 用途 | 根据结构化搜索条件返回路线方案 |
| 请求体 | `SearchRequest` |
| 响应体 | `SearchResponse` |
| 认证 | 否 |

## AI 搜索

### POST `/api/v1/search/ai/sessions`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | `frontend/src/components/AiSearchTab/index.tsx` -> `aiSearchApi.createSession(text)` |
| 路径 | `POST /api/v1/search/ai/sessions` |
| 用途 | 创建 AI 搜索会话并处理首条用户消息 |
| 请求体 | `{ message: string }` |
| 响应体 | `AISearchResponse` |
| 认证 | 可选；带 token 时持久化会话摘要，匿名时使用进程内会话 |

### GET `/api/v1/search/ai/sessions`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范预留：`AiSearchTab` 初始化恢复历史会话 |
| 路径 | `GET /api/v1/search/ai/sessions` |
| 用途 | 获取当前用户 AI 搜索会话摘要列表 |
| 请求体 | 无 |
| 响应体 | `{ sessions: AISessionSummary[] }` |
| 认证 | 是 |

### GET `/api/v1/search/ai/sessions/{session_id}`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范预留：刷新或恢复单个 AI 会话详情 |
| 路径 | `GET /api/v1/search/ai/sessions/{session_id}` |
| 用途 | 获取单个 AI 会话完整状态 |
| 请求体 | 无 |
| 响应体 | `AISearchResponse` |
| 认证 | 否；当前读取进程内会话 |

### POST `/api/v1/search/ai/sessions/{session_id}/messages`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | `frontend/src/components/AiSearchTab/index.tsx` -> `aiSearchApi.sendMessage(sessionId, text, lang)` |
| 路径 | `POST /api/v1/search/ai/sessions/{session_id}/messages` |
| 用途 | 在已有 AI 搜索会话中追加用户消息 |
| 请求体 | `{ message: string, language?: "zh" \| "en" }` |
| 响应体 | `AISearchResponse` |
| 认证 | 可选；带 token 时同步持久化会话摘要 |

### POST `/api/v1/search/ai/sessions/{session_id}/confirm`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | `frontend/src/components/AiSearchTab/index.tsx` -> `aiSearchApi.confirm(sessionId, confirmed)` |
| 路径 | `POST /api/v1/search/ai/sessions/{session_id}/confirm` |
| 用途 | 确认执行 AI 已整理的搜索条件，或拒绝后继续调整 |
| 请求体 | `{ confirmed: boolean }` |
| 响应体 | `AISearchResponse`；确认成功时 `search_response` 包含 `SearchResponse` |
| 认证 | 可选；带 token 时同步持久化会话摘要 |

### PUT `/api/v1/search/ai/sessions/{session_id}`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范预留：`AiSearchTab/index.tsx` 的会话重命名逻辑 |
| 路径 | `PUT /api/v1/search/ai/sessions/{session_id}` |
| 用途 | 重命名 AI 搜索会话 |
| 请求体 | `{ title: string }` |
| 响应体 | `AISessionSummary` |
| 认证 | 是 |

### DELETE `/api/v1/search/ai/sessions/{session_id}`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范预留：`AiSearchTab/index.tsx` 的删除会话逻辑 |
| 路径 | `DELETE /api/v1/search/ai/sessions/{session_id}` |
| 用途 | 删除当前用户的 AI 搜索会话摘要记录 |
| 请求体 | 无 |
| 响应体 | `{ success: true }` |
| 认证 | 是 |

### POST `/api/v1/search/ai/summarize`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | `frontend/src/components/AiSearchTab/index.tsx` -> `aiSearchApi.summarize(text, lang)` |
| 路径 | `POST /api/v1/search/ai/summarize` |
| 用途 | 使用规则算法生成 AI 会话短标题 |
| 请求体 | `{ message: string, language?: string }` |
| 响应体 | `{ title: string }` |
| 认证 | 否 |

## 认证模块

### POST `/api/v1/auth/register`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`RegisterModal.tsx` 注册提交 |
| 路径 | `POST /api/v1/auth/register` |
| 用途 | 创建用户账户并返回登录 token |
| 请求体 | `{ username: string, email: string, password: string }` |
| 响应体 | `{ user: UserProfile, access_token: string, token_type: "bearer" }` |
| 认证 | 否 |

### POST `/api/v1/auth/login`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`LoginModal.tsx` 登录提交 |
| 路径 | `POST /api/v1/auth/login` |
| 用途 | 校验邮箱密码并返回登录 token |
| 请求体 | `{ email: string, password: string }` |
| 响应体 | `{ user: UserProfile, access_token: string, token_type: "bearer" }` |
| 认证 | 否 |

### POST `/api/v1/auth/logout`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`TopNav/index.tsx` -> `AuthContext.logout()` |
| 路径 | `POST /api/v1/auth/logout` |
| 用途 | 吊销当前 token 并下线当前登录设备 |
| 请求体 | 无 |
| 响应体 | `{ success: true }` |
| 认证 | 是 |

### POST `/api/v1/auth/forgot-password/check-email`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`ForgotPasswordFlowModal.tsx` 邮箱检查 |
| 路径 | `POST /api/v1/auth/forgot-password/check-email` |
| 用途 | 判断邮箱是否已注册 |
| 请求体 | `{ email: string }` |
| 响应体 | `{ registered: boolean }` |
| 认证 | 否 |

### POST `/api/v1/auth/forgot-password/send-code`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`ForgotPasswordFlowModal.tsx` / `ForgotPasswordModal.tsx` 发送验证码 |
| 路径 | `POST /api/v1/auth/forgot-password/send-code` |
| 用途 | 发送密码重置验证码；开发码固定为 `000000` |
| 请求体 | `{ email: string }` |
| 响应体 | `{ expires_in_seconds: number }` |
| 认证 | 否 |

### POST `/api/v1/auth/forgot-password/verify-code`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`ForgotPasswordFlowModal.tsx` / `ForgotPasswordModal.tsx` 验证验证码 |
| 路径 | `POST /api/v1/auth/forgot-password/verify-code` |
| 用途 | 校验验证码并返回一次性 reset token |
| 请求体 | `{ email: string, code: string }` |
| 响应体 | `{ verified: boolean, reset_token?: string }` |
| 认证 | 否 |

### POST `/api/v1/auth/forgot-password/reset`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`ForgotPasswordFlowModal.tsx` / `ForgotPasswordModal.tsx` 重置密码 |
| 路径 | `POST /api/v1/auth/forgot-password/reset` |
| 用途 | 使用 reset token 设置新密码 |
| 请求体 | `{ reset_token: string, new_password: string }` |
| 响应体 | `{ success: true }` |
| 认证 | 否 |

## 用户信息模块

### GET `/api/v1/user/profile`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`AccountPanel.tsx`、`SecurityPanel.tsx`、`TopNav/index.tsx` |
| 路径 | `GET /api/v1/user/profile` |
| 用途 | 获取当前登录用户资料 |
| 请求体 | 无 |
| 响应体 | `UserProfile` |
| 认证 | 是 |

### PUT `/api/v1/user/profile`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`AccountPanel.tsx` 保存昵称 |
| 路径 | `PUT /api/v1/user/profile` |
| 用途 | 更新用户昵称 |
| 请求体 | `{ nickname?: string }` |
| 响应体 | `UserProfile` |
| 认证 | 是 |

### POST `/api/v1/user/avatar`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`AccountPanel.tsx` 更换头像 |
| 路径 | `POST /api/v1/user/avatar` |
| 用途 | 上传当前用户头像 |
| 请求体 | `multipart/form-data`，字段名 `file`；也兼容直接上传 image body |
| 响应体 | `{ avatar_url: string }` |
| 认证 | 是 |

### GET `/api/v1/user/avatar/{user_id}`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 头像 URL 返回值可直接用于前端图片展示 |
| 路径 | `GET /api/v1/user/avatar/{user_id}` |
| 用途 | 读取用户头像二进制图片 |
| 请求体 | 无 |
| 响应体 | 图片二进制，`Content-Type` 为上传时的图片类型 |
| 认证 | 否 |

### PUT `/api/v1/user/email`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`SecurityPanel.tsx` 邮箱编辑确认 |
| 路径 | `PUT /api/v1/user/email` |
| 用途 | 修改绑定邮箱 |
| 请求体 | `{ new_email: string, code?: string }` |
| 响应体 | `UserProfile` |
| 认证 | 是 |

### PUT `/api/v1/user/password`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`SecurityPanel.tsx` 修改密码确认 |
| 路径 | `PUT /api/v1/user/password` |
| 用途 | 已登录用户修改密码 |
| 请求体 | `{ current_password: string, new_password: string }` |
| 响应体 | `{ success: true }` |
| 认证 | 是 |

## 用户偏好模块

### GET `/api/v1/user/preferences`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`AppearancePanel.tsx`、`AIHistoryPanel.tsx`、`ThemeContext.tsx`、`LocaleContext.tsx` |
| 路径 | `GET /api/v1/user/preferences` |
| 用途 | 获取当前用户持久化偏好 |
| 请求体 | 无 |
| 响应体 | `UserPreferences` |
| 认证 | 是 |

### PUT `/api/v1/user/preferences`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：主题切换、语言切换、历史保留时间设置 |
| 路径 | `PUT /api/v1/user/preferences` |
| 用途 | 部分更新用户偏好并返回合并后的完整偏好 |
| 请求体 | `Partial<UserPreferences>` |
| 响应体 | `UserPreferences` |
| 认证 | 是 |

### GET `/api/v1/user/import-platforms`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`ImportPanel.tsx` 初始化平台开关 |
| 路径 | `GET /api/v1/user/import-platforms` |
| 用途 | 获取导入平台启用状态 |
| 请求体 | 无 |
| 响应体 | `{ platforms: Record<string, boolean> }` |
| 认证 | 是 |

### PUT `/api/v1/user/import-platforms`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`ImportPanel.tsx` toggle 开关 |
| 路径 | `PUT /api/v1/user/import-platforms` |
| 用途 | 更新单个平台启用状态 |
| 请求体 | `{ platform_key: string, enabled: boolean }` |
| 响应体 | `{ platforms: Record<string, boolean> }` |
| 认证 | 是 |

## 收藏模块

### GET `/api/v1/user/favorites`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`FavoritesContext.tsx` / `FavoritesTab` 初始化收藏 |
| 路径 | `GET /api/v1/user/favorites` |
| 用途 | 获取当前用户收藏路线列表 |
| 请求体 | 无 |
| 响应体 | `{ favorites: RoutePlan[], total: number }` |
| 认证 | 是 |

### POST `/api/v1/user/favorites`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`FavoritesContext.tsx` 的 `toggleFavorite` 添加收藏 |
| 路径 | `POST /api/v1/user/favorites` |
| 用途 | 收藏一条完整路线 |
| 请求体 | `{ route: RoutePlan }` |
| 响应体 | `{ id: string, created_at: string }` |
| 认证 | 是 |

### DELETE `/api/v1/user/favorites/{route_id}`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`FavoritesContext.tsx` 的 `toggleFavorite` 取消收藏 |
| 路径 | `DELETE /api/v1/user/favorites/{route_id}` |
| 用途 | 删除当前用户的一条收藏 |
| 请求体 | 无 |
| 响应体 | `{ success: true }` |
| 认证 | 是 |

## 设备管理模块

### GET `/api/v1/user/devices`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`DevicesPanel.tsx` |
| 路径 | `GET /api/v1/user/devices` |
| 用途 | 获取当前用户登录设备列表 |
| 请求体 | 无 |
| 响应体 | `{ devices: DeviceInfo[] }` |
| 认证 | 是 |

### DELETE `/api/v1/user/devices/{device_id}`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`DevicesPanel.tsx` 下线设备操作 |
| 路径 | `DELETE /api/v1/user/devices/{device_id}` |
| 用途 | 下线指定设备并吊销对应 token |
| 请求体 | 无 |
| 响应体 | `{ success: true }` |
| 认证 | 是 |

## 预订模块

### POST `/api/v1/bookings`

| 项目 | 内容 |
| --- | --- |
| 调用位置 | 前端规范目标：`SearchTab/ResultList.tsx` 的“立即预订”按钮 |
| 路径 | `POST /api/v1/bookings` |
| 用途 | 创建本地预订订单；初版不调用真实票务平台 |
| 请求体 | `{ route_id: string, legs: Leg[] }` |
| 响应体 | `{ booking_id: string, status: string, redirect_url?: string \| null }` |
| 认证 | 是 |

## 数据模型摘要

### `SearchRequest`

```typescript
interface SearchRequest {
  from_city: string
  to_city: string
  travel_date: string
  optimization_target: 'price' | 'time' | 'transfer' | 'balanced'
  max_transfers?: number
  min_transfers?: number
  preferred_transport_types?: ('flight' | 'train')[]
  max_price?: number
  max_total_duration_minutes?: number
  excluded_cities?: string[]
  required_transfer_cities?: string[]
  departure_time_range?: { start: string; end: string }
  arrival_time_range?: { start: string; end: string }
  allow_overnight?: boolean
}
```

### `SearchResponse`

```typescript
interface SearchResponse {
  search_id: string
  routes: RoutePlan[]
  total_count: number
  total: number
}
```

### `RoutePlan`

```typescript
interface RoutePlan {
  id: string
  total_price: number
  total_duration_minutes: number
  transfer_count: number
  legs: Leg[]
  score?: number
  tag?: string
}
```

### `Leg`

```typescript
interface Leg {
  transport_type: 'flight' | 'train'
  from_city: string
  to_city: string
  from_city_en: string
  to_city_en: string
  from_station: string
  to_station: string
  from_station_en: string
  to_station_en: string
  departure_date: string
  departure_time: string
  arrival_date: string
  arrival_time: string
  duration_minutes: number
  price: number
  company: string
  flight_train_no: string
  platform?: string
}
```

### `AISearchResponse`

```typescript
interface AISearchResponse {
  session_id: string
  status: 'collecting' | 'awaiting_confirmation' | 'completed'
  assistant_message: string
  conversation: { role: 'user' | 'assistant'; content: string }[]
  parsed_request: Partial<SearchRequest>
  final_request: SearchRequest | null
  missing_fields: string[]
  summary: string
  ready_for_confirmation: boolean
  search_executed: boolean
  search_response: SearchResponse | null
}
```

### `UserProfile`

```typescript
interface UserProfile {
  id: string
  username: string
  email: string
  nickname?: string
  avatar_url?: string
  created_at: string
}
```

### `UserPreferences`

```typescript
interface UserPreferences {
  theme: 'light' | 'dark'
  language: 'zh' | 'en'
  search_retention_days: number
  chat_retention_days: number
  import_platforms: Record<string, boolean>
}
```

### `DeviceInfo`

```typescript
interface DeviceInfo {
  id: string
  device_name: string
  ip_address: string
  login_time: string
  is_current: boolean
}
```

### `AISessionSummary`

```typescript
interface AISessionSummary {
  session_id: string
  title: string
  status: 'collecting' | 'awaiting_confirmation' | 'completed'
  last_message_preview: string
  created_at: string
  updated_at: string
}
```

