// 城市和站点类型
export interface City {
  code: string;
  name: string;
  name_en: string;
  country: string;
}

export interface Station {
  code: string;
  name: string;
  city_code: string;
  type: 'airport' | 'train_station' | 'bus_station';
}

// 交通类型
export type TransportType = 'flight' | 'train';

// 优化目标
export type OptimizationTarget = 'price' | 'time' | 'transfer' | 'balanced';

// 行程段
export interface Leg {
  transport_type: TransportType;
  from_city: string;
  to_city: string;
  from_city_en: string;
  to_city_en: string;
  from_station: string;
  to_station: string;
  from_station_en: string;
  to_station_en: string;
  departure_date: string;
  departure_time: string;
  arrival_date: string;
  arrival_time: string;
  duration_minutes: number;
  price: number;
  company: string;
  flight_train_no: string;
  platform?: string;
}

// 路线方案
export interface RoutePlan {
  id: string;
  total_price: number;
  total_duration_minutes: number;
  transfer_count: number;
  score?: number;
  tag?: string;
  legs: Leg[];
}

// 搜索请求
export interface SearchRequest {
  from_city: string;
  to_city: string;
  travel_date: string;
  optimization_target: OptimizationTarget;
  max_transfers?: number;
  min_transfers?: number;
  preferred_transport_types?: TransportType[];
  max_price?: number;
  max_total_duration_minutes?: number;
  excluded_cities?: string[];
  required_transfer_cities?: string[];
  departure_time_range?: { start: string; end: string };
  arrival_time_range?: { start: string; end: string };
  allow_overnight?: boolean;
}

// 搜索响应
export interface SearchResponse {
  search_id?: string;
  routes: RoutePlan[];
  total_count: number;
  total?: number;
  data_mode?: 'mock';
  data_notice?: string;
  mock_source_date?: string;
}

// 城市列表响应
export interface CityListResponse {
  cities: City[];
}

// AI 消息
export interface AiMessage {
  role: 'user' | 'assistant';
  content: string;
}

// AI 会话响应
export interface AiSessionResponse {
  session_id: string;
  status: 'collecting' | 'awaiting_confirmation' | 'completed';
  assistant_message: string;
  conversation: AiMessage[];
  parsed_request: Partial<SearchRequest>;
  final_request: SearchRequest | null;
  missing_fields: string[];
  summary: string;
  ready_for_confirmation: boolean;
  search_executed: boolean;
  search_response: SearchResponse | null;
}

// AI 确认请求
export interface AiConfirmRequest {
  confirmed: boolean;
}

export type SessionDuration = 'day' | 'week' | 'month' | 'half_year' | 'year' | 'forever';

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  email_verified: boolean;
  nickname?: string | null;
  avatar_url?: string | null;
  created_at: string;
}

export interface AuthLoginRequest {
  email: string;
  password: string;
  session_duration?: SessionDuration;
}

export interface AuthRegisterRequest {
  username: string;
  email: string;
  password: string;
  email_verification_token: string;
  session_duration?: SessionDuration;
}

export interface AuthTokenResponse {
  user: UserProfile;
  access_token: string;
  token_type: 'bearer';
  expires_at: string | null;
  session_duration: SessionDuration;
}

export interface SessionDurationUpdateResponse {
  expires_at: string | null;
  session_duration: SessionDuration;
}

export interface AuthSession {
  user: UserProfile;
  expiresAt: string | null;
  sessionDuration: SessionDuration;
}

export interface DeviceInfo {
  id: string;
  device_name: string;
  ip_address: string;
  login_time: string;
  is_current: boolean;
}

export interface DeviceListResponse {
  devices: DeviceInfo[];
}

export interface ForgotPasswordCheckEmailResponse {
  registered: boolean;
}

export interface ForgotPasswordSendCodeResponse {
  expires_in_seconds: number;
}

export interface ForgotPasswordVerifyCodeResponse {
  verified: boolean;
  reset_token: string | null;
}

export type EmailVerificationPurpose = 'register' | 'verify_current' | 'change_email';

export interface EmailVerificationSendResponse {
  expires_in_seconds: number;
}

export interface EmailVerificationVerifyResponse {
  verified: boolean;
  verification_token: string | null;
}
