import axios from 'axios';
import type {
  SearchRequest,
  SearchResponse,
  CityListResponse,
  City,
  AiSessionResponse,
  AiConfirmRequest,
} from '../types';

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
  getCities: async (keyword?: string): Promise<City[]> => {
    const response = await apiClient.get<CityListResponse>('/cities', {
      params: keyword ? { keyword } : undefined,
    });
    return response.data.cities;
  },
};

// AI 搜索 API
export const aiSearchApi = {
  createSession: async (message: string): Promise<AiSessionResponse> => {
    const response = await apiClient.post<AiSessionResponse>('/search/ai/sessions', { message });
    return response.data;
  },

  sendMessage: async (sessionId: string, message: string, language?: string): Promise<AiSessionResponse> => {
    const response = await apiClient.post<AiSessionResponse>(
      `/search/ai/sessions/${sessionId}/messages`,
      { message, language }
    );
    return response.data;
  },

  confirm: async (sessionId: string, confirmed: boolean): Promise<AiSessionResponse> => {
    const response = await apiClient.post<AiSessionResponse>(
      `/search/ai/sessions/${sessionId}/confirm`,
      { confirmed } as AiConfirmRequest
    );
    return response.data;
  },
};

export default apiClient;
