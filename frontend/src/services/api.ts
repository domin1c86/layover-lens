import axios from 'axios';
import type { SearchRequest, SearchResponse, CityListResponse, City } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 搜索 API
export const searchApi = {
  search: async (request: SearchRequest): Promise<SearchResponse> => {
    const response = await apiClient.post<SearchResponse>('/search', request);
    return response.data;
  },
};

// 城市 API
export const cityApi = {
  getCities: async (): Promise<City[]> => {
    const response = await apiClient.get<CityListResponse>('/cities');
    return response.data.cities;
  },
};

export default apiClient;
