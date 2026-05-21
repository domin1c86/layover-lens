import { useState } from 'react';
import type { City, OptimizationTarget, TransportType } from '../../types';
import './SearchBar.css';

interface SearchBarProps {
  cities: City[];
  fromCity: string;
  toCity: string;
  date: string;
  optimize: OptimizationTarget;
  onFromChange: (val: string) => void;
  onToChange: (val: string) => void;
  onDateChange: (val: string) => void;
  onOptimizeChange: (val: OptimizationTarget) => void;
  onSearch: (advancedFilters: AdvancedFilters) => void;
  loading: boolean;
}

export interface AdvancedFilters {
  transfer: 'any' | 'yes' | 'no';
  transferCity: string;
  transferTime: 'any' | 'short' | 'medium' | 'long';
  priceMin: string;
  priceMax: string;
  transportTypes: TransportType[];
}

const OPTIMIZE_LABELS: Record<OptimizationTarget, string> = {
  price: '价格优先',
  time: '时间优先',
  transfer: '少换乘',
  balanced: '综合推荐',
};

export default function SearchBar({
  cities,
  fromCity,
  toCity,
  date,
  optimize,
  onFromChange,
  onToChange,
  onDateChange,
  onOptimizeChange,
  onSearch,
  loading,
}: SearchBarProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [advanced, setAdvanced] = useState<AdvancedFilters>({
    transfer: 'any',
    transferCity: '',
    transferTime: 'any',
    priceMin: '',
    priceMax: '',
    transportTypes: ['flight', 'train'],
  });

  const handleSearch = () => {
    onSearch(advanced);
  };

  const updateAdvanced = <K extends keyof AdvancedFilters>(key: K, val: AdvancedFilters[K]) => {
    setAdvanced((prev) => ({ ...prev, [key]: val }));
  };

  const toggleTransport = (type: TransportType) => {
    setAdvanced((prev) => {
      const has = prev.transportTypes.includes(type);
      const next = has
        ? prev.transportTypes.filter((t) => t !== type)
        : [...prev.transportTypes, type];
      return { ...prev, transportTypes: next.length ? next : prev.transportTypes };
    });
  };

  return (
    <div className="search-combo">
      <div className="search-bar">
        <div className="search-bar__segment">
          <span className="search-bar__label">出发地</span>
          <select
            className="search-bar__value active"
            value={fromCity}
            onChange={(e) => onFromChange(e.target.value)}
          >
            {cities.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div className="search-bar__segment">
          <span className="search-bar__label">目的地</span>
          <select
            className="search-bar__value active"
            value={toCity}
            onChange={(e) => onToChange(e.target.value)}
          >
            {cities.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div className="search-bar__segment">
          <span className="search-bar__label">日期</span>
          <input
            type="date"
            className="search-bar__value active"
            value={date}
            onChange={(e) => onDateChange(e.target.value)}
            style={{ color: 'inherit', fontSize: '14px' }}
          />
        </div>
        <div className="search-bar__segment">
          <span className="search-bar__label">优化目标</span>
          <select
            className="search-bar__value"
            value={optimize}
            onChange={(e) => onOptimizeChange(e.target.value as OptimizationTarget)}
          >
            {(['balanced', 'price', 'time', 'transfer'] as OptimizationTarget[]).map((o) => (
              <option key={o} value={o}>
                {OPTIMIZE_LABELS[o]}
              </option>
            ))}
          </select>
        </div>
        <button className="search-bar__orb" onClick={handleSearch} disabled={loading} title="搜索">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
        </button>
      </div>

      <div className={`advanced-search ${drawerOpen ? '' : 'hidden'}`}>
        <div className="advanced-search__row">
          <div className="advanced-search__field">
            <label>是否中转</label>
            <select value={advanced.transfer} onChange={(e) => updateAdvanced('transfer', e.target.value as AdvancedFilters['transfer'])}>
              <option value="any">不限</option>
              <option value="yes">是</option>
              <option value="no">否</option>
            </select>
          </div>
          <div className={`advanced-search__field ${advanced.transfer !== 'yes' ? 'hidden' : ''}`}>
            <label>中转地偏好</label>
            <input
              type="text"
              placeholder="例如：南京"
              value={advanced.transferCity}
              onChange={(e) => updateAdvanced('transferCity', e.target.value)}
            />
          </div>
          <div className={`advanced-search__field ${advanced.transfer !== 'yes' ? 'hidden' : ''}`}>
            <label>中转停留时间</label>
            <select value={advanced.transferTime} onChange={(e) => updateAdvanced('transferTime', e.target.value as AdvancedFilters['transferTime'])}>
              <option value="any">不限</option>
              <option value="short">1小时以内</option>
              <option value="medium">1-3小时</option>
              <option value="long">3小时以上</option>
            </select>
          </div>
        </div>
        <div className="advanced-search__row">
          <div className="advanced-search__field">
            <label>偏好价格区间</label>
            <div className="advanced-search__price">
              <input
                type="number"
                placeholder="最低"
                value={advanced.priceMin}
                onChange={(e) => updateAdvanced('priceMin', e.target.value)}
              />
              <span>—</span>
              <input
                type="number"
                placeholder="最高"
                value={advanced.priceMax}
                onChange={(e) => updateAdvanced('priceMax', e.target.value)}
              />
            </div>
          </div>
          <div className="advanced-search__field">
            <label>偏好交通工具</label>
            <div className="advanced-search__transport">
              <label>
                <input type="checkbox" checked={advanced.transportTypes.includes('flight')} onChange={() => toggleTransport('flight')} />
                航班
              </label>
              <label>
                <input type="checkbox" checked={advanced.transportTypes.includes('train')} onChange={() => toggleTransport('train')} />
                火车
              </label>
            </div>
          </div>
        </div>
      </div>

      <div className="advanced-search-toggle" onClick={() => setDrawerOpen(!drawerOpen)}>
        <span>高级搜索</span>
        <svg className={`advanced-search__arrow ${drawerOpen ? 'open' : ''}`} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </div>
    </div>
  );
}
