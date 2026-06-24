import { useState, useRef, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import type { City, OptimizationTarget, TransportType } from '../../types';
import { useLocale } from '../../context/LocaleContext';
import { Icon } from '../../icons';
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
  morphLayoutId?: string;
}

export interface AdvancedFilters {
  transfer: 'any' | 'yes' | 'no';
  transferCities: string[];
  transferTime: 'any' | 'short' | 'medium' | 'long';
  transferCountMin: string;
  transferCountMax: string;
  priceMin: string;
  priceMax: string;
  transportTypes: TransportType[];
}

/* ================= Custom Pickers ================= */

const HOT_CITY_NAMES = new Set([
  '北京', '上海', '广州', '深圳', '杭州', '成都', '南京', '武汉', '西安', '重庆',
  '郑州', '长沙', '天津', '苏州', '沈阳', '青岛', '厦门', '合肥',
]);

function CityPicker({ cities, value, onChange, onClose, isOpen, cityGroups, lang }: {
  cities: City[];
  value: string;
  onChange: (val: string) => void;
  onClose: () => void;
  isOpen: boolean;
  cityGroups: { key: string; label: string }[];
  lang: 'zh' | 'en';
}) {
  const [activeGroup, setActiveGroup] = useState('hot');

  const filtered = useMemo(() => {
    if (activeGroup === 'hot') {
      return cities.filter((c) => HOT_CITY_NAMES.has(c.name));
    }
    return cities.filter((c) => {
      if (HOT_CITY_NAMES.has(c.name)) return false;
      const first = (c.name_en.charAt(0) || '').toLowerCase();
      for (const g of cityGroups) {
        if (g.key !== 'hot' && g.key.includes(first)) return g.key === activeGroup;
      }
      return activeGroup === 'uvwxyz';
    });
  }, [cities, activeGroup, cityGroups]);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="picker-panel city-picker"
          initial={{ opacity: 0, y: -24, scale: 0.9, x: '-50%' }}
          animate={{ opacity: 1, y: 0, scale: 1, x: '-50%' }}
          exit={{ opacity: 0, y: -12, scale: 0.95, x: '-50%' }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          onClick={(e: React.MouseEvent) => e.stopPropagation()}
        >
          <div className="city-picker__tabs">
            {cityGroups.map((g) => (
              <div
                key={g.key}
                className={`city-picker__tab ${activeGroup === g.key ? 'active' : ''}`}
                onClick={() => setActiveGroup(g.key)}
              >
                {g.label}
              </div>
            ))}
          </div>
          <div className="city-picker__grid">
            {filtered.map((c) => (
              <div
                key={c.code}
                className={`picker-item ${c.code === value ? 'selected' : ''}`}
                onClick={() => { onChange(c.code); onClose(); }}
              >
                {lang === 'en' ? c.name_en : c.name}
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function MultiCityPicker({ cities, selected, onChange, onClose, isOpen, cityGroups, confirmLabel, lang }: {
  cities: City[];
  selected: string[];
  onChange: (val: string[]) => void;
  onClose: () => void;
  isOpen: boolean;
  cityGroups: { key: string; label: string }[];
  confirmLabel: string;
  lang: 'zh' | 'en';
}) {
  const [activeGroup, setActiveGroup] = useState('hot');

  const filtered = useMemo(() => {
    if (activeGroup === 'hot') {
      return cities.filter((c) => HOT_CITY_NAMES.has(c.name));
    }
    return cities.filter((c) => {
      if (HOT_CITY_NAMES.has(c.name)) return false;
      const first = (c.name_en.charAt(0) || '').toLowerCase();
      for (const g of cityGroups) {
        if (g.key !== 'hot' && g.key.includes(first)) return g.key === activeGroup;
      }
      return activeGroup === 'uvwxyz';
    });
  }, [cities, activeGroup, cityGroups]);

  const toggleCity = (code: string) => {
    const next = selected.includes(code)
      ? selected.filter((c) => c !== code)
      : [...selected, code];
    onChange(next);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="picker-panel city-picker"
          initial={{ opacity: 0, y: -24, scale: 0.9, x: '-50%' }}
          animate={{ opacity: 1, y: 0, scale: 1, x: '-50%' }}
          exit={{ opacity: 0, y: -12, scale: 0.95, x: '-50%' }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          onClick={(e: React.MouseEvent) => e.stopPropagation()}
        >
          <div className="city-picker__tabs">
            {cityGroups.map((g) => (
              <div
                key={g.key}
                className={`city-picker__tab ${activeGroup === g.key ? 'active' : ''}`}
                onClick={() => setActiveGroup(g.key)}
              >
                {g.label}
              </div>
            ))}
          </div>
          <div className="city-picker__grid">
            {filtered.map((c) => (
              <div
                key={c.code}
                className={`picker-item ${selected.includes(c.code) ? 'selected' : ''}`}
                onClick={() => toggleCity(c.code)}
              >
                {lang === 'en' ? c.name_en : c.name}
              </div>
            ))}
          </div>
          <div className="city-picker__footer">
            <button className="city-picker__confirm" onClick={onClose}>{confirmLabel}</button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function OptPicker({ value, onChange, onClose, isOpen, labels }: {
  value: OptimizationTarget;
  onChange: (val: OptimizationTarget) => void;
  onClose: () => void;
  isOpen: boolean;
  labels: Record<OptimizationTarget, string>;
}) {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="picker-panel opt-picker"
          initial={{ opacity: 0, y: -24, scale: 0.9, x: '-50%' }}
          animate={{ opacity: 1, y: 0, scale: 1, x: '-50%' }}
          exit={{ opacity: 0, y: -12, scale: 0.95, x: '-50%' }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          onClick={(e: React.MouseEvent) => e.stopPropagation()}
        >
          {(['balanced', 'price', 'time', 'transfer'] as OptimizationTarget[]).map((o) => (
            <div
              key={o}
              className={`picker-item ${o === value ? 'selected' : ''}`}
              onClick={() => { onChange(o); onClose(); }}
            >
              {labels[o]}
            </div>
          ))}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function SelectPicker<T extends string>({ options, value, onChange, onClose, isOpen }: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (val: T) => void;
  onClose: () => void;
  isOpen: boolean;
}) {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="picker-panel opt-picker"
          initial={{ opacity: 0, y: -24, scale: 0.9, x: '-50%' }}
          animate={{ opacity: 1, y: 0, scale: 1, x: '-50%' }}
          exit={{ opacity: 0, y: -12, scale: 0.95, x: '-50%' }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          onClick={(e: React.MouseEvent) => e.stopPropagation()}
        >
          {options.map((o) => (
            <div
              key={o.value}
              className={`picker-item ${o.value === value ? 'selected' : ''}`}
              onClick={() => { onChange(o.value); onClose(); }}
            >
              {o.label}
            </div>
          ))}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function CalendarPicker({ value, onChange, onClose, isOpen, lang, t }: {
  value: string;
  onChange: (val: string) => void;
  onClose: () => void;
  isOpen: boolean;
  lang: 'zh' | 'en';
  t: (key: string, vars?: Record<string, string>) => string;
}) {
  const [viewDate, setViewDate] = useState(() => {
    const d = value ? new Date(value + 'T00:00:00') : new Date();
    return new Date(d.getFullYear(), d.getMonth(), 1);
  });

  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const startOffset = firstDay === 0 ? 6 : firstDay - 1;
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const days: (number | null)[] = [];
  for (let i = 0; i < startOffset; i++) days.push(null);
  for (let i = 1; i <= daysInMonth; i++) days.push(i);

  const handleDayClick = (day: number) => {
    const iso = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    onChange(iso);
    onClose();
  };

  const isSelected = (day: number) => {
    if (!value) return false;
    const d = new Date(value + 'T00:00:00');
    return d.getFullYear() === year && d.getMonth() === month && d.getDate() === day;
  };

  const isToday = (day: number) => {
    const t = new Date();
    return t.getFullYear() === year && t.getMonth() === month && t.getDate() === day;
  };

  const prevMonth = () => setViewDate(new Date(year, month - 1, 1));
  const nextMonth = () => setViewDate(new Date(year, month + 1, 1));

  const weekDays = lang === 'en'
    ? ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    : ['一', '二', '三', '四', '五', '六', '日'];

  const formatDateLabel = (iso: string) => {
    const d = new Date(iso + 'T00:00:00');
    if (lang === 'en') {
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
    return `${d.getMonth() + 1}月${d.getDate()}日`;
  };

  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);
  const dayAfterTomorrow = new Date(today);
  dayAfterTomorrow.setDate(today.getDate() + 2);

  const fmtQuick = (d: Date) => {
    if (lang === 'en') {
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
    return `${d.getMonth() + 1}月${d.getDate()}日`;
  };
  const isoQuick = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

  const quickOptions = [
    { label: t('calendar.today'), sub: fmtQuick(today), date: isoQuick(today) },
    { label: t('calendar.tomorrow'), sub: fmtQuick(tomorrow), date: isoQuick(tomorrow) },
    { label: t('calendar.dayAfterTomorrow'), sub: fmtQuick(dayAfterTomorrow), date: isoQuick(dayAfterTomorrow) },
  ];

  const headerMonth = lang === 'en'
    ? viewDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
    : `${year}年${month + 1}月`;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="picker-panel calendar-picker"
          initial={{ opacity: 0, y: -24, scale: 0.9, x: '-50%' }}
          animate={{ opacity: 1, y: 0, scale: 1, x: '-50%' }}
          exit={{ opacity: 0, y: -12, scale: 0.95, x: '-50%' }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          onClick={(e: React.MouseEvent) => e.stopPropagation()}
        >
          <div className="calendar-picker__layout">
            <div className="calendar-quick-select">
              {quickOptions.map((q) => (
                <div
                  key={q.label}
                  className="calendar-quick-card"
                  onClick={() => { onChange(q.date); onClose(); }}
                >
                  <div className="calendar-quick-card__title">{q.label}</div>
                  <div className="calendar-quick-card__sub">{q.sub}</div>
                </div>
              ))}
            </div>
            <div className="calendar-main">
              <div className="calendar-header">
                <button type="button" onClick={prevMonth} aria-label={t('calendar.prevMonth')}>‹</button>
                <span>{headerMonth}</span>
                <button type="button" onClick={nextMonth} aria-label={t('calendar.nextMonth')}>›</button>
              </div>
              <div className="calendar-weekdays">
                {weekDays.map((d) => <span key={d}>{d}</span>)}
              </div>
              <div className="calendar-days">
                {days.map((day, i) => (
                  <div
                    key={i}
                    className={`calendar-day ${day === null ? 'empty' : ''} ${day !== null && isSelected(day) ? 'selected' : ''} ${day !== null && isToday(day) ? 'today' : ''}`}
                    onClick={() => day !== null && handleDayClick(day)}
                  >
                    {day}
                  </div>
                ))}
              </div>
              {value && (
                <div className="calendar-footer">
                  {t('calendar.selected', { date: formatDateLabel(value) })}
                </div>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ================= Main Component ================= */

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
  morphLayoutId,
}: SearchBarProps) {
  const { lang, t } = useLocale();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [advanced, setAdvanced] = useState<AdvancedFilters>({
    transfer: 'any',
    transferCities: [],
    transferTime: 'any',
    transferCountMin: '',
    transferCountMax: '',
    priceMin: '',
    priceMax: '',
    transportTypes: ['flight', 'train'],
  });

  const [fromOpen, setFromOpen] = useState(false);
  const [toOpen, setToOpen] = useState(false);
  const [dateOpen, setDateOpen] = useState(false);
  const [optOpen, setOptOpen] = useState(false);
  const [transferOpen, setTransferOpen] = useState(false);
  const [transferPickerOpen, setTransferPickerOpen] = useState(false);
  const [transferTimePickerOpen, setTransferTimePickerOpen] = useState(false);

  const fromRef = useRef<HTMLDivElement>(null);
  const toRef = useRef<HTMLDivElement>(null);
  const dateRef = useRef<HTMLDivElement>(null);
  const optRef = useRef<HTMLDivElement>(null);
  const transferRef = useRef<HTMLDivElement>(null);
  const transferPickerRef = useRef<HTMLDivElement>(null);
  const transferTimePickerRef = useRef<HTMLDivElement>(null);
  const advancedRef = useRef<HTMLDivElement>(null);
  const toggleRef = useRef<HTMLDivElement>(null);

  const optimizeLabels: Record<OptimizationTarget, string> = {
    price: t('optimize.price'),
    time: t('optimize.time'),
    transfer: t('optimize.transfer'),
    balanced: t('optimize.balanced'),
  };

  const transferOptions: { value: AdvancedFilters['transfer']; label: string }[] = [
    { value: 'any', label: t('searchBar.transferAny') },
    { value: 'yes', label: t('searchBar.transferYes') },
    { value: 'no', label: t('searchBar.transferNo') },
  ];

  const transferTimeOptions: { value: AdvancedFilters['transferTime']; label: string }[] = [
    { value: 'any', label: t('searchBar.transferAny') },
    { value: 'short', label: t('searchBar.transferTimeShort') },
    { value: 'medium', label: t('searchBar.transferTimeMedium') },
    { value: 'long', label: t('searchBar.transferTimeLong') },
  ];

  const cityGroups = [
    { key: 'hot', label: t('cityGroups.hot') },
    { key: 'abcd', label: 'ABCD' },
    { key: 'efgh', label: 'EFGH' },
    { key: 'ijkl', label: 'IJKL' },
    { key: 'mnop', label: 'MNOP' },
    { key: 'qrst', label: 'QRST' },
    { key: 'uvwxyz', label: 'UVWXYZ' },
  ];

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      const target = e.target as Node;

      // Toggle click: close internal pickers and let toggle onClick handle drawerOpen
      if (toggleRef.current?.contains(target)) {
        setTransferPickerOpen(false);
        setTransferOpen(false);
        setTransferTimePickerOpen(false);
        return;
      }

      // Internal pickers of advanced search
      const internalPickerRefs = [transferPickerRef, transferRef, transferTimePickerRef];
      const internalPickerSetters = [setTransferPickerOpen, setTransferOpen, setTransferTimePickerOpen];

      const clickInsideAnyInternalPicker = internalPickerRefs.some((ref) => ref.current?.contains(target));
      const anyInternalPickerOpen = transferPickerOpen || transferOpen || transferTimePickerOpen;

      // Close internal pickers if clicked outside
      internalPickerRefs.forEach((ref, i) => {
        if (!ref.current?.contains(target)) {
          internalPickerSetters[i](false);
        }
      });

      // If any internal picker was open and click was outside all of them,
      // only close the picker(s), don't close the panel
      if (anyInternalPickerOpen && !clickInsideAnyInternalPicker) {
        return;
      }

      // Close search bar pickers
      const searchBarPickerRefs = [fromRef, toRef, dateRef, optRef];
      const searchBarPickerSetters = [setFromOpen, setToOpen, setDateOpen, setOptOpen];
      searchBarPickerRefs.forEach((ref, i) => {
        if (!ref.current?.contains(target)) {
          searchBarPickerSetters[i](false);
        }
      });

      // Check if click is inside search bar segments (not the orb)
      const clickInsideSearchBarSegments = searchBarPickerRefs.some((ref) => ref.current?.contains(target));

      // Close advanced panel only if no internal pickers were open,
      // panel is open, click is outside panel, outside toggle, and outside search bar segments
      if (
        drawerOpen &&
        advancedRef.current &&
        !advancedRef.current.contains(target) &&
        !clickInsideSearchBarSegments
      ) {
        setDrawerOpen(false);
        setTransferPickerOpen(false);
        setTransferOpen(false);
        setTransferTimePickerOpen(false);
      }
    }
    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, [drawerOpen, transferPickerOpen, transferOpen, transferTimePickerOpen]);

  const togglePicker = (key: 'from' | 'to' | 'date' | 'opt') => {
    setFromOpen(key === 'from' ? !fromOpen : false);
    setToOpen(key === 'to' ? !toOpen : false);
    setDateOpen(key === 'date' ? !dateOpen : false);
    setOptOpen(key === 'opt' ? !optOpen : false);
  };

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

  const fromName = cities.find((c) => c.code === fromCity)?.[lang === 'en' ? 'name_en' : 'name'] || fromCity;
  const toName = cities.find((c) => c.code === toCity)?.[lang === 'en' ? 'name_en' : 'name'] || toCity;

  const formatDateLabel = (iso: string) => {
    if (!iso) return t('searchBar.selectDate');
    const d = new Date(iso + 'T00:00:00');
    if (lang === 'en') {
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }
    return `${d.getMonth() + 1}月${d.getDate()}日`;
  };

  const formatTransferCitiesLabel = (codes: string[]) => {
    if (codes.length === 0) return t('searchBar.selectTransferCities');
    const names = codes.map((code) => {
      const city = cities.find((c) => c.code === code);
      return city ? (lang === 'en' ? city.name_en : city.name) : code;
    });
    return names.join('、');
  };

  const hasOpenSegment = fromOpen || toOpen || dateOpen || optOpen;

  return (
    <div className="search-combo">
      <motion.div
        layoutId={morphLayoutId}
        className={`search-bar ${hasOpenSegment ? 'has-open-segment' : ''}`}
        transition={{ type: 'spring', stiffness: 420, damping: 38, mass: 0.9 }}
      >
        <div className={`search-bar__segment ${fromOpen ? 'open' : ''}`} ref={fromRef} onClick={() => togglePicker('from')}>
          <span className="search-bar__label">{t('searchBar.from')}</span>
          <span className="search-bar__value active">{fromName}</span>
          <CityPicker
            cities={cities}
            value={fromCity}
            onChange={onFromChange}
            onClose={() => setFromOpen(false)}
            isOpen={fromOpen}
            cityGroups={cityGroups}
            lang={lang}
          />
        </div>
        <div className={`search-bar__segment ${toOpen ? 'open' : ''}`} ref={toRef} onClick={() => togglePicker('to')}>
          <span className="search-bar__label">{t('searchBar.to')}</span>
          <span className="search-bar__value active">{toName}</span>
          <CityPicker
            cities={cities}
            value={toCity}
            onChange={onToChange}
            onClose={() => setToOpen(false)}
            isOpen={toOpen}
            cityGroups={cityGroups}
            lang={lang}
          />
        </div>
        <div className={`search-bar__segment ${dateOpen ? 'open' : ''}`} ref={dateRef} onClick={() => togglePicker('date')}>
          <span className="search-bar__label">{t('searchBar.date')}</span>
          <span className="search-bar__value active">{formatDateLabel(date)}</span>
          <CalendarPicker
            value={date}
            onChange={onDateChange}
            onClose={() => setDateOpen(false)}
            isOpen={dateOpen}
            lang={lang}
            t={t}
          />
        </div>
        <div className={`search-bar__segment ${optOpen ? 'open' : ''}`} ref={optRef} onClick={() => togglePicker('opt')}>
          <span className="search-bar__label">{t('searchBar.optimize')}</span>
          <span className="search-bar__value">{optimizeLabels[optimize]}</span>
          <OptPicker
            value={optimize}
            onChange={onOptimizeChange}
            onClose={() => setOptOpen(false)}
            isOpen={optOpen}
            labels={optimizeLabels}
          />
        </div>
        <button className="search-bar__orb" onClick={handleSearch} disabled={loading} title={t('searchBar.search')}>
          <Icon name="actions.search" size={20} />
        </button>
      </motion.div>

      <AnimatePresence>
        {drawerOpen && (
          <motion.div
            className={`advanced-search ${(transferOpen || transferPickerOpen || transferTimePickerOpen) ? 'overflow-visible' : ''}`}
            ref={advancedRef}
            initial={{ height: 0, opacity: 0, paddingTop: 0, paddingBottom: 0, marginTop: 0 }}
            animate={{ height: 'auto', opacity: 1, paddingTop: 48, paddingBottom: 32, marginTop: -32 }}
            exit={{ height: 0, opacity: 0, paddingTop: 0, paddingBottom: 0, marginTop: 0 }}
            transition={{ duration: 0.35, ease: [0, 0, 1, 1] }}
          >
        <div className="advanced-search__row">
          <div className="advanced-search__field">
            <label>{t('searchBar.transfer')}</label>
            <div
              className="advanced-search__trigger"
              ref={transferPickerRef}
              onClick={() => setTransferPickerOpen(!transferPickerOpen)}
            >
              <span className="active">{transferOptions.find((o) => o.value === advanced.transfer)?.label}</span>
              <SelectPicker
                options={transferOptions}
                value={advanced.transfer}
                onChange={(val) => updateAdvanced('transfer', val)}
                onClose={() => setTransferPickerOpen(false)}
                isOpen={transferPickerOpen}
              />
            </div>
          </div>
          <div className={`advanced-search__field ${advanced.transfer === 'no' ? 'hidden' : ''}`}>
            <label>{t('searchBar.transferCities')}</label>
            <div
              className="advanced-search__trigger"
              ref={transferRef}
              onClick={() => setTransferOpen(!transferOpen)}
            >
              <span className={advanced.transferCities.length > 0 ? 'active' : ''}>
                {formatTransferCitiesLabel(advanced.transferCities)}
              </span>
              <MultiCityPicker
                cities={cities}
                selected={advanced.transferCities}
                onChange={(val) => updateAdvanced('transferCities', val)}
                onClose={() => setTransferOpen(false)}
                isOpen={transferOpen}
                cityGroups={cityGroups}
                confirmLabel={t('searchBar.confirm')}
                lang={lang}
              />
            </div>
          </div>
          <div className={`advanced-search__field ${advanced.transfer === 'no' ? 'hidden' : ''}`}>
            <label>{t('searchBar.transferTime')}</label>
            <div
              className="advanced-search__trigger"
              ref={transferTimePickerRef}
              onClick={() => setTransferTimePickerOpen(!transferTimePickerOpen)}
            >
              <span className="active">{transferTimeOptions.find((o) => o.value === advanced.transferTime)?.label}</span>
              <SelectPicker
                options={transferTimeOptions}
                value={advanced.transferTime}
                onChange={(val) => updateAdvanced('transferTime', val)}
                onClose={() => setTransferTimePickerOpen(false)}
                isOpen={transferTimePickerOpen}
              />
            </div>
          </div>
          <div className={`advanced-search__field ${advanced.transfer === 'no' ? 'hidden' : ''}`}>
            <label>{t('searchBar.transferCount')}</label>
            <div className="advanced-search__price">
              <input
                type="number"
                placeholder={t('searchBar.min')}
                value={advanced.transferCountMin}
                onChange={(e) => updateAdvanced('transferCountMin', e.target.value)}
              />
              <span>—</span>
              <input
                type="number"
                placeholder={t('searchBar.max')}
                value={advanced.transferCountMax}
                onChange={(e) => updateAdvanced('transferCountMax', e.target.value)}
              />
            </div>
          </div>
        </div>
        <div className="advanced-search__row">
          <div className="advanced-search__field">
            <label>{t('searchBar.priceRange')}</label>
            <div className="advanced-search__price">
              <input
                type="number"
                placeholder={t('searchBar.priceMin')}
                value={advanced.priceMin}
                onChange={(e) => updateAdvanced('priceMin', e.target.value)}
              />
              <span>—</span>
              <input
                type="number"
                placeholder={t('searchBar.priceMax')}
                value={advanced.priceMax}
                onChange={(e) => updateAdvanced('priceMax', e.target.value)}
              />
            </div>
          </div>
          <div className="advanced-search__field">
            <label>{t('searchBar.transportType')}</label>
            <div className="advanced-search__transport">
              <label>
                <input type="checkbox" checked={advanced.transportTypes.includes('flight')} onChange={() => toggleTransport('flight')} />
                {t('searchBar.flight')}
              </label>
              <label>
                <input type="checkbox" checked={advanced.transportTypes.includes('train')} onChange={() => toggleTransport('train')} />
                {t('searchBar.train')}
              </label>
            </div>
          </div>
        </div>
      </motion.div>
        )}
    </AnimatePresence>

      <div className="advanced-search-toggle" ref={toggleRef} onClick={() => setDrawerOpen(!drawerOpen)}>
        <span>{t('searchBar.advanced')}</span>
        <motion.svg
          className="advanced-search__arrow"
          animate={{ rotate: drawerOpen ? 180 : 0 }}
          transition={{ duration: 0.3 }}
          width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        >
          <polyline points="6 9 12 15 18 9" />
        </motion.svg>
      </div>
    </div>
  );
}
