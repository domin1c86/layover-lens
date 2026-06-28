import { useEffect, useMemo, useRef, useState } from 'react';
import { animate, motion, useMotionValue, useMotionValueEvent, useScroll, useTransform } from 'motion/react';
import type { City, OptimizationTarget } from '../../types';
import { useLocale } from '../../context/LocaleContext';
import SearchBar, { type AdvancedFilters } from '../SearchTab/SearchBar';
import './FloatingSearchDock.css';

const DESKTOP_SCROLL_RANGE = 160;
const MOBILE_SCROLL_RANGE = 96;
const MOBILE_BREAKPOINT = 744;
const DESKTOP_MANUAL_RECOMPACT_DELTA = 96;
const MOBILE_MANUAL_RECOMPACT_DELTA = 64;

interface FloatingSearchDockProps {
  behavior?: 'scroll' | 'temporary';
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
  onCompactChange?: (compact: boolean) => void;
  autoCollapseMs?: number;
}

function estimateTextWidth(text: string, font: string) {
  if (typeof document !== 'undefined') {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    if (context) {
      context.font = font;
      return context.measureText(text).width;
    }
  }

  return Array.from(text).reduce((total, char) => {
    if (/[\u4e00-\u9fff]/.test(char)) return total + 15;
    if (/[A-Z]/.test(char)) return total + 8;
    if (/\s/.test(char)) return total + 4;
    return total + 7;
  }, 0);
}

function formatCompactDateLabel(iso: string, lang: 'zh' | 'en') {
  if (!iso) return lang === 'en' ? 'Select date' : '选择日期';
  const date = new Date(`${iso}T00:00:00`);
  if (lang === 'en') {
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }
  return `${date.getMonth() + 1}月${date.getDate()}日`;
}

function getCityDisplayName(cities: City[], code: string, lang: 'zh' | 'en') {
  const city = cities.find((item) => item.code === code);
  return city?.[lang === 'en' ? 'name_en' : 'name'] || code;
}

function getViewportMetrics(compactLabel = '') {
  const width = window.innerWidth;
  const isMobile = width <= MOBILE_BREAKPOINT;
  const mobilePadding = width <= 360 ? 12 : 16;
  const expandedWidth = isMobile ? width - mobilePadding * 2 : Math.min(720, width - 160);
  const compactSummaryWidth = compactLabel
    ? Math.ceil(estimateTextWidth(compactLabel, '600 13px MiSans, Inter, system-ui, sans-serif') + 26 + 8 + 28)
    : 236;
  const compactWidth = isMobile
    ? Math.min(expandedWidth - 16, Math.max(width <= 360 ? 188 : 204, compactSummaryWidth))
    : Math.min(420, Math.max(280, width - 604));

  return {
    width,
    isMobile,
    expandedWidth,
    compactWidth,
    expandedTop: isMobile ? 72 : 84,
    compactTop: isMobile ? 72 : 16,
    expandedHeight: isMobile ? 84 : 96,
    compactHeight: isMobile ? 42 : 48,
  };
}

export default function FloatingSearchDock({
  behavior = 'scroll',
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
  onCompactChange,
  autoCollapseMs = 15000,
}: FloatingSearchDockProps) {
  const { lang } = useLocale();
  const compactLabel = useMemo(() => {
    const fromName = getCityDisplayName(cities, fromCity, lang);
    const toName = getCityDisplayName(cities, toCity, lang);
    return `${fromName} → ${toName} · ${formatCompactDateLabel(date, lang)}`;
  }, [cities, date, fromCity, lang, toCity]);
  const [metrics, setMetrics] = useState(() => getViewportMetrics(compactLabel));
  const [mode, setMode] = useState<'expanded' | 'compact-summary'>('expanded');
  const [temporaryExpanded, setTemporaryExpanded] = useState(false);
  const [manualExpanded, setManualExpanded] = useState(false);
  const [isPastTop, setIsPastTop] = useState(() => window.scrollY > 2);
  const mobileOutsideCollapsedRef = useRef(false);
  const [forceCloseOverlaysSignal, setForceCloseOverlaysSignal] = useState(0);
  const dockRef = useRef<HTMLDivElement>(null);
  const { scrollY } = useScroll();
  const manualCollapseProgress = useMotionValue(0);
  const scrollSessionActiveRef = useRef(false);
  const scrollSessionTimeoutRef = useRef<number | undefined>();
  const autoCollapseTimeoutRef = useRef<number | undefined>();
  const manualExpandAnimationRef = useRef<ReturnType<typeof animate> | null>(null);
  const manualTargetCompactRef = useRef(false);
  const outsideCollapseAtRef = useRef(0);
  const lastScrollYRef = useRef(window.scrollY);
  const isPastTopRef = useRef(window.scrollY > 2);
  const lastCompactRef = useRef(false);
  const manualExpandedAtRef = useRef(0);

  useEffect(() => {
    const handleResize = () => setMetrics(getViewportMetrics(compactLabel));
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [compactLabel]);

  useEffect(() => {
    const updatePastTop = () => {
      const nextIsPastTop = window.scrollY > 2;
      if (nextIsPastTop === isPastTopRef.current) return;
      isPastTopRef.current = nextIsPastTop;
      setIsPastTop(nextIsPastTop);
    };

    updatePastTop();
    window.addEventListener('scroll', updatePastTop, { passive: true });
    return () => window.removeEventListener('scroll', updatePastTop);
  }, []);

  const scrollRange = metrics.isMobile ? MOBILE_SCROLL_RANGE : DESKTOP_SCROLL_RANGE;
  const compactThreshold = metrics.isMobile ? 0.58 : 0.72;
  const progress = useTransform(scrollY, [0, scrollRange], [0, 1], { clamp: true });
  const top = useTransform(progress, [0, 1], [metrics.expandedTop, metrics.compactTop]);
  const width = useTransform(progress, [0, 1], [metrics.expandedWidth, metrics.compactWidth]);
  const height = useTransform(progress, [0, 1], [metrics.expandedHeight, metrics.compactHeight]);
  const borderRadius = useTransform(progress, [0, 1], [24, 999]);
  const manualTop = useTransform(manualCollapseProgress, [0, 1], [metrics.expandedTop, metrics.compactTop]);
  const manualWidth = useTransform(manualCollapseProgress, [0, 1], [metrics.expandedWidth, metrics.compactWidth]);
  const manualHeight = useTransform(manualCollapseProgress, [0, 1], [metrics.expandedHeight, metrics.compactHeight]);
  const manualBorderRadius = useTransform(manualCollapseProgress, [0, 1], [24, 999]);

  useMotionValueEvent(scrollY, 'change', (current) => {
    if (behavior !== 'scroll') return;

    const nextIsPastTop = current > 2;
    if (nextIsPastTop !== isPastTopRef.current) {
      isPastTopRef.current = nextIsPastTop;
      setIsPastTop(nextIsPastTop);
    }

    if (metrics.isMobile && mobileOutsideCollapsedRef.current && current <= 2) {
      mobileOutsideCollapsedRef.current = false;
      lastCompactRef.current = false;
      setMode('expanded');
      onCompactChange?.(false);
    }

    if (manualExpanded) {
      const recompactDelta = metrics.isMobile ? MOBILE_MANUAL_RECOMPACT_DELTA : DESKTOP_MANUAL_RECOMPACT_DELTA;
      if (Math.abs(current - lastScrollYRef.current) > 2) {
        manualExpandAnimationRef.current?.stop();
        manualExpandAnimationRef.current = null;
      }
      const nextManualProgress = Math.min(1, Math.max(0, (current - manualExpandedAtRef.current) / recompactDelta));
      manualCollapseProgress.set(nextManualProgress);

      if (nextManualProgress >= 1) {
        setManualExpanded(false);
        setMode('compact-summary');
        lastCompactRef.current = true;
        onCompactChange?.(!metrics.isMobile);
      }
    }

    if (Math.abs(current - lastScrollYRef.current) > 2) {
      if (!scrollSessionActiveRef.current) {
        scrollSessionActiveRef.current = true;
        setForceCloseOverlaysSignal((value) => value + 1);
      }

      if (scrollSessionTimeoutRef.current !== undefined) {
        window.clearTimeout(scrollSessionTimeoutRef.current);
      }
      scrollSessionTimeoutRef.current = window.setTimeout(() => {
        scrollSessionActiveRef.current = false;
        scrollSessionTimeoutRef.current = undefined;
      }, 160);
    }

    lastScrollYRef.current = current;
  });

  useMotionValueEvent(progress, 'change', (latest) => {
    if (behavior !== 'scroll') return;
    if (manualExpanded) return;

    if (metrics.isMobile && mobileOutsideCollapsedRef.current && window.scrollY > 2) {
      if (mode !== 'compact-summary') {
        lastCompactRef.current = true;
        setMode('compact-summary');
        onCompactChange?.(false);
      }
      return;
    }

    const nextCompact = latest >= compactThreshold;
    if (nextCompact !== lastCompactRef.current) {
      lastCompactRef.current = nextCompact;
      setMode(nextCompact ? 'compact-summary' : 'expanded');
      onCompactChange?.(nextCompact && !metrics.isMobile);
    }
  });

  useEffect(() => {
    if (behavior !== 'scroll') {
      lastCompactRef.current = true;
      setMode(temporaryExpanded ? 'expanded' : 'compact-summary');
      onCompactChange?.(true);
      return;
    }

    if (manualExpanded) {
      lastCompactRef.current = false;
      if (manualTargetCompactRef.current) {
        setMode('compact-summary');
        onCompactChange?.(!metrics.isMobile);
      } else {
        setMode('expanded');
        onCompactChange?.(false);
      }
      return;
    }

    if (metrics.isMobile && mobileOutsideCollapsedRef.current && window.scrollY > 2) {
      lastCompactRef.current = true;
      setMode('compact-summary');
      onCompactChange?.(false);
      return;
    }

    const currentProgress = Math.min(1, Math.max(0, window.scrollY / scrollRange));
    const nextCompact = currentProgress >= compactThreshold;
    lastCompactRef.current = nextCompact;
    setMode(nextCompact ? 'compact-summary' : 'expanded');
    onCompactChange?.(nextCompact && !metrics.isMobile);
  }, [behavior, compactThreshold, manualExpanded, metrics.isMobile, onCompactChange, scrollRange, temporaryExpanded]);

  useEffect(() => {
    if (behavior !== 'temporary') return;

    if (autoCollapseTimeoutRef.current !== undefined) {
      window.clearTimeout(autoCollapseTimeoutRef.current);
      autoCollapseTimeoutRef.current = undefined;
    }

    if (temporaryExpanded) {
      autoCollapseTimeoutRef.current = window.setTimeout(() => {
        setTemporaryExpanded(false);
        setForceCloseOverlaysSignal((value) => value + 1);
      }, autoCollapseMs);
    }

    return () => {
      if (autoCollapseTimeoutRef.current !== undefined) {
        window.clearTimeout(autoCollapseTimeoutRef.current);
        autoCollapseTimeoutRef.current = undefined;
      }
    };
  }, [autoCollapseMs, behavior, temporaryExpanded]);

  const collapseScrollDock = () => {
    const currentProgress = Math.min(1, Math.max(0, window.scrollY / scrollRange));
    manualExpandAnimationRef.current?.stop();
    manualCollapseProgress.set(currentProgress);
    mobileOutsideCollapsedRef.current = metrics.isMobile;
    manualTargetCompactRef.current = true;
    lastCompactRef.current = true;
    setManualExpanded(true);
    setMode('compact-summary');
    setForceCloseOverlaysSignal((value) => value + 1);
    onCompactChange?.(!metrics.isMobile);

    const controls = animate(manualCollapseProgress, 1, {
      type: 'spring',
      stiffness: 420,
      damping: 38,
      mass: 0.9,
    });
    manualExpandAnimationRef.current = controls;
    void controls.then(() => {
      if (manualExpandAnimationRef.current !== controls) return;
      setManualExpanded(false);
      manualTargetCompactRef.current = false;
      manualExpandAnimationRef.current = null;
    });
  };

  useEffect(() => {
    const shouldListenForOutsideClick = behavior === 'temporary'
      ? temporaryExpanded
      : metrics.isMobile && mode === 'expanded';

    if (!shouldListenForOutsideClick) return;

    const handleOutsideInteraction = (event: MouseEvent | PointerEvent) => {
      const target = event.target as Node;
      if (dockRef.current?.contains(target)) return;
      if (document.querySelector('.top-nav')?.contains(target)) return;

      if (behavior === 'temporary') {
        setTemporaryExpanded(false);
        setForceCloseOverlaysSignal((value) => value + 1);
        return;
      }

      if (window.scrollY <= 2) return;
      const now = Date.now();
      if (now - outsideCollapseAtRef.current < 180) return;
      outsideCollapseAtRef.current = now;
      collapseScrollDock();
    };

    document.addEventListener('pointerdown', handleOutsideInteraction, true);
    document.addEventListener('mousedown', handleOutsideInteraction, true);
    document.addEventListener('click', handleOutsideInteraction, true);
    return () => {
      document.removeEventListener('pointerdown', handleOutsideInteraction, true);
      document.removeEventListener('mousedown', handleOutsideInteraction, true);
      document.removeEventListener('click', handleOutsideInteraction, true);
    };
  }, [behavior, metrics.isMobile, mode, scrollRange, temporaryExpanded]);

  useEffect(() => {
    return () => {
      if (scrollSessionTimeoutRef.current !== undefined) {
        window.clearTimeout(scrollSessionTimeoutRef.current);
      }
      if (autoCollapseTimeoutRef.current !== undefined) {
        window.clearTimeout(autoCollapseTimeoutRef.current);
      }
      manualExpandAnimationRef.current?.stop();
      onCompactChange?.(false);
    };
  }, [onCompactChange]);

  const variant = metrics.isMobile ? 'mobile' : 'desktop';

  const dockClassName = useMemo(
    () => `floating-search-dock floating-search-dock--${variant} floating-search-dock--${mode} floating-search-dock--${behavior}`,
    [behavior, mode, variant],
  );

  const handleRequestExpand = () => {
    if (behavior === 'temporary') {
      setTemporaryExpanded(true);
      setForceCloseOverlaysSignal((value) => value + 1);
      return;
    }

    mobileOutsideCollapsedRef.current = false;
    manualTargetCompactRef.current = false;
    manualExpandedAtRef.current = window.scrollY;
    const currentProgress = Math.min(1, Math.max(0, window.scrollY / scrollRange));
    manualExpandAnimationRef.current?.stop();
    manualCollapseProgress.set(currentProgress);
    lastCompactRef.current = false;
    setManualExpanded(true);
    setMode('expanded');
    setForceCloseOverlaysSignal((value) => value + 1);
    onCompactChange?.(false);
    manualExpandAnimationRef.current = animate(manualCollapseProgress, 0, {
      type: 'spring',
      stiffness: 420,
      damping: 38,
      mass: 0.9,
    });
  };

  const temporaryLayout = behavior === 'temporary'
    ? {
      top: temporaryExpanded ? metrics.expandedTop : metrics.compactTop,
      width: temporaryExpanded ? metrics.expandedWidth : metrics.compactWidth,
      height: temporaryExpanded ? metrics.expandedHeight : metrics.compactHeight,
      borderRadius: temporaryExpanded ? 24 : 999,
    }
    : undefined;

  const shouldRenderOutsideHitarea = metrics.isMobile
    && mode === 'expanded'
    && (
      (behavior === 'temporary' && temporaryExpanded)
      || (behavior === 'scroll' && isPastTop)
    );

  const handleOutsideHitareaClick = () => {
    if (behavior === 'temporary') {
      setTemporaryExpanded(false);
      setForceCloseOverlaysSignal((value) => value + 1);
      return;
    }

    if (window.scrollY <= 2) return;
    collapseScrollDock();
  };

  return (
    <motion.div
      ref={dockRef}
      className={dockClassName}
      style={behavior === 'scroll'
        ? (manualExpanded
          ? { top: manualTop, width: manualWidth, height: manualHeight, borderRadius: manualBorderRadius }
          : { top, width, height, borderRadius })
        : undefined}
      animate={temporaryLayout}
      transition={{ type: 'spring', stiffness: 420, damping: 38, mass: 0.9 }}
    >
      {shouldRenderOutsideHitarea && (
        <button
          type="button"
          className="floating-search-dock__outside-hitarea"
          aria-label="Collapse search"
          onClick={handleOutsideHitareaClick}
        />
      )}
      <SearchBar
        cities={cities}
        fromCity={fromCity}
        toCity={toCity}
        date={date}
        optimize={optimize}
        onFromChange={onFromChange}
        onToChange={onToChange}
        onDateChange={onDateChange}
        onOptimizeChange={onOptimizeChange}
        onSearch={onSearch}
        loading={loading}
        mode={mode}
        variant={variant}
        onRequestExpand={handleRequestExpand}
        forceCloseOverlaysSignal={forceCloseOverlaysSignal}
      />
    </motion.div>
  );
}
