import { useState, useEffect } from 'react';
import type { RoutePlan } from '../../types';
import ResultList from '../SearchTab/ResultList';
import './FavoritesTab.css';

const STORAGE_KEY = 'layover-lens-favorites';

function loadFavorites(): RoutePlan[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveFavorites(routes: RoutePlan[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(routes));
  } catch {
    // Quota exceeded or private mode
  }
}

export function useFavorites() {
  const [favorites, setFavorites] = useState<RoutePlan[]>(loadFavorites);

  useEffect(() => {
    saveFavorites(favorites);
  }, [favorites]);

  const toggleFavorite = (route: RoutePlan) => {
    setFavorites((prev) => {
      const exists = prev.some((r) => r.id === route.id);
      if (exists) return prev.filter((r) => r.id !== route.id);
      return [...prev, route];
    });
  };

  const isFavorite = (routeId: string) => favorites.some((r) => r.id === routeId);

  return { favorites, toggleFavorite, isFavorite };
}

export default function FavoritesTab() {
  const { favorites } = useFavorites();

  return (
    <div className="favorites">
      <div className="container">
        <h2 className="results-header">我的收藏</h2>
        <ResultList
          routes={favorites}
          loading={false}
          error=""
          searched={true}
          header={favorites.length > 0 ? `共 ${favorites.length} 条收藏` : undefined}
        />
        {favorites.length === 0 && (
          <div className="empty-state">
            <div className="empty-state__icon">❤️</div>
            <div className="empty-state__title">暂无收藏的行程</div>
            <div className="empty-state__subtitle">在搜索结果中点击收藏按钮添加</div>
          </div>
        )}
      </div>
    </div>
  );
}
