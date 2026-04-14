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
  from_station: string;
  to_station: string;
  departure_time: string;
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
  legs: Leg[];
}

// 搜索请求
export interface SearchRequest {
  from_city: string;
  to_city: string;
  travel_date: string;
  optimization_target: OptimizationTarget;
  max_transfers?: number;
}

// 搜索响应
export interface SearchResponse {
  routes: RoutePlan[];
  total_count: number;
}

// 城市列表响应
export interface CityListResponse {
  cities: City[];
}
