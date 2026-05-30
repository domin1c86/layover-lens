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
