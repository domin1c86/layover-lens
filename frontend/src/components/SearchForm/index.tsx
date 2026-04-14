import { useState, useEffect } from 'react';
import type { City, OptimizationTarget } from '../../types';
import { cityApi } from '../../services/api';
import './SearchForm.css';

interface SearchFormProps {
  onSearch: (params: {
    from_city: string;
    to_city: string;
    travel_date: string;
    optimization_target: OptimizationTarget;
  }) => void;
  loading: boolean;
}

const OPTIMIZATION_OPTIONS: { value: OptimizationTarget; label: string }[] = [
  { value: 'price', label: '价格优先' },
  { value: 'time', label: '时间优先' },
  { value: 'transfer', label: '少换乘' },
  { value: 'balanced', label: '综合推荐' },
];

export function SimpleSearchForm({ onSearch, loading }: SearchFormProps) {
  const [cities, setCities] = useState<City[]>([]);
  const [fromCity, setFromCity] = useState('');
  const [toCity, setToCity] = useState('');
  const [travelDate, setTravelDate] = useState(() => {
    const today = new Date();
    return today.toISOString().split('T')[0];
  });
  const [optimizationTarget, setOptimizationTarget] = useState<OptimizationTarget>('balanced');
  const [error, setError] = useState('');

  useEffect(() => {
    loadCities();
  }, []);

  const loadCities = async () => {
    try {
      const data = await cityApi.getCities();
      setCities(data);
      if (data.length > 0) {
        setFromCity(data[0].code);
        if (data.length > 1) {
          setToCity(data[1].code);
        }
      }
    } catch (err) {
      setError('加载城市列表失败');
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!fromCity || !toCity || !travelDate) {
      setError('请填写完整的搜索信息');
      return;
    }

    if (fromCity === toCity) {
      setError('出发城市和目的城市不能相同');
      return;
    }

    setError('');
    onSearch({
      from_city: fromCity,
      to_city: toCity,
      travel_date: travelDate,
      optimization_target: optimizationTarget,
    });
  };

  const handleSwapCities = () => {
    setFromCity(toCity);
    setToCity(fromCity);
  };

  return (
    <form className="search-form" onSubmit={handleSubmit}>
      <div className="search-form__row">
        <div className="search-form__field">
          <label htmlFor="from-city">出发城市</label>
          <select
            id="from-city"
            value={fromCity}
            onChange={(e) => setFromCity(e.target.value)}
            disabled={loading}
          >
            {cities.map((city) => (
              <option key={city.code} value={city.code}>
                {city.name}
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          className="search-form__swap-btn"
          onClick={handleSwapCities}
          disabled={loading}
          title="交换城市"
        >
          ⇄
        </button>

        <div className="search-form__field">
          <label htmlFor="to-city">目的城市</label>
          <select
            id="to-city"
            value={toCity}
            onChange={(e) => setToCity(e.target.value)}
            disabled={loading}
          >
            {cities.map((city) => (
              <option key={city.code} value={city.code}>
                {city.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="search-form__row">
        <div className="search-form__field">
          <label htmlFor="travel-date">出发日期</label>
          <input
            type="date"
            id="travel-date"
            value={travelDate}
            onChange={(e) => setTravelDate(e.target.value)}
            disabled={loading}
            min={new Date().toISOString().split('T')[0]}
          />
        </div>

        <div className="search-form__field">
          <label htmlFor="optimization">优化目标</label>
          <select
            id="optimization"
            value={optimizationTarget}
            onChange={(e) => setOptimizationTarget(e.target.value as OptimizationTarget)}
            disabled={loading}
          >
            {OPTIMIZATION_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <div className="search-form__error">{error}</div>}

      <button
        type="submit"
        className="search-form__submit-btn"
        disabled={loading}
      >
        {loading ? '搜索中...' : '搜索路线'}
      </button>
    </form>
  );
}
