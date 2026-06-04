import { useState, useRef, useEffect, useMemo } from 'react';
import { X, RotateCw } from 'lucide-react';
import { useConfigStore } from '../../stores/configStore';
import { useDataStore } from '../../stores/dataStore';
import { parseSlashDateRange, formatSlashDateRange } from '../../lib/utils/dateUtils';
import {
  mergeUploadedDataBounds,
  listQuarterOptions,
  listMonthOptions,
  listWowWeekOptions,
  listYearOptions,
} from '../../lib/utils/analysisPeriodSelectors';

function useClickOutside(ref, handler) {
  useEffect(() => {
    const listener = (e) => {
      if (!ref.current || ref.current.contains(e.target)) return;
      handler();
    };
    document.addEventListener('mousedown', listener);
    return () => document.removeEventListener('mousedown', listener);
  }, [ref, handler]);
}

const COMPARE_TABS = [
  { id: 'pvp', label: 'Pre vs Post' },
  { id: 'qoq', label: 'QoQ' },
  { id: 'mom', label: 'MoM' },
  { id: 'wow', label: 'WoW' },
];

const SINGLE_TABS = [
  { id: 'singleRange', label: 'Range' },
  { id: 'singleWeek', label: 'Week' },
  { id: 'singleMonth', label: 'Month' },
  { id: 'singleQuarter', label: 'Quarter' },
  { id: 'singleYear', label: 'Year' },
];

function isSingleMode(mode) {
  return String(mode || '').startsWith('single');
}

export default function DateFilterDropdown({ onClose, onApply }) {
  const config = useConfigStore();
  const ddFinancial = useDataStore((s) => s.ddFinancial);
  const ueFinancial = useDataStore((s) => s.ueFinancial);

  const bounds = useMemo(() => mergeUploadedDataBounds(ddFinancial, ueFinancial), [ddFinancial, ueFinancial]);
  const hasBounds = !!(bounds.min && bounds.max);

  const quarterOpts = useMemo(() => listQuarterOptions(bounds), [bounds]);
  const monthOpts = useMemo(() => listMonthOptions(bounds), [bounds]);
  const weekOpts = useMemo(() => listWowWeekOptions(bounds, 52), [bounds]);
  const yearOpts = useMemo(() => listYearOptions(bounds), [bounds]);

  const initialMode = config.dateAnalysisMode || 'pvp';
  const [periodKind, setPeriodKind] = useState(isSingleMode(initialMode) ? 'single' : 'compare');
  const [mode, setMode] = useState(initialMode);

  const [preRange, setPreRange] = useState(() => formatSlashDateRange(config.ddPreStart, config.ddPreEnd));
  const [postRange, setPostRange] = useState(() => formatSlashDateRange(config.ddPostStart, config.ddPostEnd));
  const [singleRange, setSingleRange] = useState(() => formatSlashDateRange(config.ddPostStart, config.ddPostEnd));

  const [qoqPreId, setQoqPreId] = useState('');
  const [qoqPostId, setQoqPostId] = useState('');
  const [momPreId, setMomPreId] = useState('');
  const [momPostId, setMomPostId] = useState('');
  const [wowPreId, setWowPreId] = useState('');
  const [wowPostId, setWowPostId] = useState('');

  const [singleWeekId, setSingleWeekId] = useState('');
  const [singleMonthId, setSingleMonthId] = useState('');
  const [singleQuarterId, setSingleQuarterId] = useState('');
  const [singleYearId, setSingleYearId] = useState('');

  const defaultQoqPre = quarterOpts[Math.max(0, quarterOpts.length - 2)]?.id ?? '';
  const defaultQoqPost = quarterOpts[quarterOpts.length - 1]?.id ?? '';
  const defaultMomPre = monthOpts[Math.max(0, monthOpts.length - 2)]?.id ?? '';
  const defaultMomPost = monthOpts[monthOpts.length - 1]?.id ?? '';
  const defaultWowPost = weekOpts.find((w) => w.weekIndex === 0)?.id ?? weekOpts[0]?.id ?? '';
  const defaultWowPre =
    weekOpts.find((w) => w.weekIndex === -1)?.id
    ?? [...weekOpts].filter((w) => w.weekIndex < 0).sort((a, b) => b.weekIndex - a.weekIndex)[0]?.id
    ?? (weekOpts.length > 1 ? weekOpts[1]?.id : '')
    ?? defaultWowPost;
  const defaultSingleWeek = defaultWowPost;
  const defaultSingleMonth = defaultMomPost;
  const defaultSingleQuarter = defaultQoqPost;
  const defaultSingleYear = yearOpts[yearOpts.length - 1]?.id ?? '';

  const ref = useRef(null);
  useClickOutside(ref, onClose);

  const applyDates = (preStart, preEnd, postStart, postEnd) => {
    config.setDdDates(preStart, preEnd, postStart, postEnd);
    if (!config.syncDates) {
      config.setUeDates(preStart, preEnd, postStart, postEnd);
    }
  };

  const applySinglePeriod = (start, end) => {
    applyDates(start, end, start, end);
  };

  const switchKind = (kind) => {
    setPeriodKind(kind);
    if (kind === 'single') {
      if (!isSingleMode(mode)) setMode('singleRange');
    } else if (isSingleMode(mode)) {
      setMode('pvp');
    }
  };

  const handleApply = () => {
    if (periodKind === 'single') {
      if (mode === 'singleRange') {
        const r = parseSlashDateRange(singleRange);
        if (!r) return;
        applySinglePeriod(r.start, r.end);
      } else if (mode === 'singleWeek') {
        const w = weekOpts.find((x) => x.id === (singleWeekId || defaultSingleWeek));
        if (!w) return;
        applySinglePeriod(w.start, w.end);
      } else if (mode === 'singleMonth') {
        const m = monthOpts.find((x) => x.id === (singleMonthId || defaultSingleMonth));
        if (!m) return;
        applySinglePeriod(m.start, m.end);
      } else if (mode === 'singleQuarter') {
        const q = quarterOpts.find((x) => x.id === (singleQuarterId || defaultSingleQuarter));
        if (!q) return;
        applySinglePeriod(q.start, q.end);
      } else if (mode === 'singleYear') {
        const y = yearOpts.find((x) => x.id === (singleYearId || defaultSingleYear));
        if (!y) return;
        applySinglePeriod(y.start, y.end);
      }
      config.setDateAnalysisMode(mode);
      onApply();
      onClose();
      return;
    }

    if (mode === 'pvp') {
      const pre = parseSlashDateRange(preRange);
      const post = parseSlashDateRange(postRange);
      if (!pre || !post) return;
      applyDates(pre.start, pre.end, post.start, post.end);
    } else if (mode === 'qoq') {
      const preId = qoqPreId || defaultQoqPre;
      const postId = qoqPostId || defaultQoqPost;
      const pre = quarterOpts.find((q) => q.id === preId);
      const post = quarterOpts.find((q) => q.id === postId);
      if (!pre || !post) return;
      applyDates(pre.start, pre.end, post.start, post.end);
    } else if (mode === 'mom') {
      const preId = momPreId || defaultMomPre;
      const postId = momPostId || defaultMomPost;
      const pre = monthOpts.find((m) => m.id === preId);
      const post = monthOpts.find((m) => m.id === postId);
      if (!pre || !post) return;
      applyDates(pre.start, pre.end, post.start, post.end);
    } else if (mode === 'wow') {
      const preId = wowPreId || defaultWowPre;
      const postId = wowPostId || defaultWowPost;
      const pre = weekOpts.find((w) => w.id === preId);
      const post = weekOpts.find((w) => w.id === postId);
      if (!pre || !post) return;
      applyDates(pre.start, pre.end, post.start, post.end);
    }
    config.setDateAnalysisMode(mode);
    onApply();
    onClose();
  };

  const canApplyCompare =
    mode === 'pvp'
      ? !!(parseSlashDateRange(preRange) && parseSlashDateRange(postRange))
      : mode === 'qoq'
        ? hasBounds && quarterOpts.length >= 1
        : mode === 'mom'
          ? hasBounds && monthOpts.length >= 1
          : mode === 'wow'
            ? hasBounds && weekOpts.length >= 1
            : false;

  const canApplySingle =
    mode === 'singleRange'
      ? !!parseSlashDateRange(singleRange)
      : mode === 'singleWeek'
        ? hasBounds && weekOpts.length >= 1
        : mode === 'singleMonth'
          ? hasBounds && monthOpts.length >= 1
          : mode === 'singleQuarter'
            ? hasBounds && quarterOpts.length >= 1
            : mode === 'singleYear'
              ? hasBounds && yearOpts.length >= 1
              : false;

  const canApply = periodKind === 'compare' ? canApplyCompare : canApplySingle;

  const activeTabs = periodKind === 'compare' ? COMPARE_TABS : SINGLE_TABS;

  return (
    <div
      ref={ref}
      className="absolute top-full right-0 mt-1 w-[min(100vw-1rem,480px)] max-w-[480px] bg-[var(--surface)] border border-[var(--border)] rounded-xl shadow-lg z-50 p-4"
    >
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-[var(--text)]">Analysis periods</h4>
        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded hover:bg-[var(--surface-2)] cursor-pointer text-[var(--text-muted)]"
        >
          <X size={14} />
        </button>
      </div>

      <div className="mb-3">
        <label className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">
          Operator name
        </label>
        <input
          type="text"
          value={config.operatorName || ''}
          onChange={(e) => config.setOperatorName(e.target.value)}
          placeholder="e.g. Acme Restaurants"
          className="mt-1 w-full px-2.5 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
        />
        <p className="mt-1 text-[10px] text-[var(--text-subtle)]">Used across exported reports (cover, header, footer).</p>
      </div>

      <div className="flex gap-1 p-0.5 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] mb-2">
        <button
          type="button"
          onClick={() => switchKind('compare')}
          className={`flex-1 px-2 py-1.5 rounded-md text-[11px] font-medium cursor-pointer
            ${periodKind === 'compare'
              ? 'bg-[var(--surface)] text-[var(--text)] shadow-sm border border-[var(--border)]'
              : 'text-[var(--text-muted)] hover:text-[var(--text)]'
            }`}
        >
          Compare
        </button>
        <button
          type="button"
          onClick={() => switchKind('single')}
          className={`flex-1 px-2 py-1.5 rounded-md text-[11px] font-medium cursor-pointer
            ${periodKind === 'single'
              ? 'bg-[var(--surface)] text-[var(--text)] shadow-sm border border-[var(--border)]'
              : 'text-[var(--text-muted)] hover:text-[var(--text)]'
            }`}
        >
          Single period
        </button>
      </div>

      <div className="flex flex-wrap gap-1 p-0.5 rounded-lg bg-[var(--surface-2)] border border-[var(--border)] mb-3">
        {activeTabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setMode(t.id)}
            className={`flex-1 min-w-[4.5rem] px-2 py-1.5 rounded-md text-[11px] font-medium transition-colors cursor-pointer
              ${mode === t.id
                ? 'bg-[var(--surface)] text-[var(--text)] shadow-sm border border-[var(--border)]'
                : 'text-[var(--text-muted)] hover:text-[var(--text)]'
              }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {!hasBounds && periodKind === 'single' && mode !== 'singleRange' && (
        <p className="text-[11px] text-amber-700 dark:text-amber-300 mb-3 leading-snug">
          Upload financial data first. Week, month, quarter, and year options use dates in your files.
        </p>
      )}

      {periodKind === 'compare' && mode === 'pvp' && (
        <>
          <p className="text-[10px] text-[var(--text-subtle)] mb-3">
            Enter each range as M/D/YYYY-M/D/YYYY (e.g. 1/1/2026-1/31/2026).
          </p>
          <div className="space-y-3">
            <div>
              <label className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Pre</label>
              <input
                type="text"
                value={preRange}
                onChange={(e) => setPreRange(e.target.value)}
                placeholder="1/1/2026-1/31/2026"
                className="mt-1 w-full px-2.5 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
              />
            </div>
            <div>
              <label className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Post</label>
              <input
                type="text"
                value={postRange}
                onChange={(e) => setPostRange(e.target.value)}
                placeholder="2/1/2026-2/28/2026"
                className="mt-1 w-full px-2.5 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
              />
            </div>
          </div>
        </>
      )}

      {periodKind === 'compare' && mode === 'qoq' && (
        <div className="space-y-3">
          <p className="text-[10px] text-[var(--text-subtle)]">
            Calendar quarters that overlap your uploaded data. Pre and Post can be any two quarters.
          </p>
          <div>
            <label className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Pre quarter</label>
            <select
              value={qoqPreId || defaultQoqPre}
              onChange={(e) => setQoqPreId(e.target.value)}
              disabled={!quarterOpts.length}
              className="mt-1 w-full px-2.5 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)]"
            >
              {quarterOpts.map((q) => (
                <option key={q.id} value={q.id}>{q.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Post quarter</label>
            <select
              value={qoqPostId || defaultQoqPost}
              onChange={(e) => setQoqPostId(e.target.value)}
              disabled={!quarterOpts.length}
              className="mt-1 w-full px-2.5 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)]"
            >
              {quarterOpts.map((q) => (
                <option key={`p-${q.id}`} value={q.id}>{q.label}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {periodKind === 'compare' && mode === 'mom' && (
        <div className="space-y-3">
          <p className="text-[10px] text-[var(--text-subtle)]">Calendar months overlapping your data range.</p>
          <div>
            <label className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Pre month</label>
            <select
              value={momPreId || defaultMomPre}
              onChange={(e) => setMomPreId(e.target.value)}
              disabled={!monthOpts.length}
              className="mt-1 w-full px-2.5 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)]"
            >
              {monthOpts.map((m) => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Post month</label>
            <select
              value={momPostId || defaultMomPost}
              onChange={(e) => setMomPostId(e.target.value)}
              disabled={!monthOpts.length}
              className="mt-1 w-full px-2.5 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)]"
            >
              {monthOpts.map((m) => (
                <option key={`p-${m.id}`} value={m.id}>{m.label}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {periodKind === 'compare' && mode === 'wow' && (
        <div className="space-y-3">
          <p className="text-[10px] text-[var(--text-subtle)] leading-relaxed">
            Weeks are Mon–Sun. Week 0 is the most recent full week on or before today (capped to your data).
          </p>
          <div>
            <label className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Pre week</label>
            <select
              value={wowPreId || defaultWowPre}
              onChange={(e) => setWowPreId(e.target.value)}
              disabled={!weekOpts.length}
              className="mt-1 w-full px-2.5 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)]"
            >
              {weekOpts.map((w) => (
                <option key={w.id} value={w.id}>{w.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Post week</label>
            <select
              value={wowPostId || defaultWowPost}
              onChange={(e) => setWowPostId(e.target.value)}
              disabled={!weekOpts.length}
              className="mt-1 w-full px-2.5 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)]"
            >
              {weekOpts.map((w) => (
                <option key={`p-${w.id}`} value={w.id}>{w.label}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {periodKind === 'single' && mode === 'singleRange' && (
        <div className="space-y-3">
          <p className="text-[10px] text-[var(--text-subtle)]">
            One custom range — no comparison. Pre and Post are set to the same window.
          </p>
          <div>
            <label className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Date range</label>
            <input
              type="text"
              value={singleRange}
              onChange={(e) => setSingleRange(e.target.value)}
              placeholder="1/1/2026-3/31/2026"
              className="mt-1 w-full px-2.5 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)] focus:outline-none focus:border-[var(--accent)]"
            />
          </div>
        </div>
      )}

      {periodKind === 'single' && mode === 'singleWeek' && (
        <div className="space-y-3">
          <p className="text-[10px] text-[var(--text-subtle)]">Pick one Mon–Sun week. No Pre vs Post comparison.</p>
          <div>
            <label className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Week</label>
            <select
              value={singleWeekId || defaultSingleWeek}
              onChange={(e) => setSingleWeekId(e.target.value)}
              disabled={!weekOpts.length}
              className="mt-1 w-full px-2.5 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)]"
            >
              {weekOpts.map((w) => (
                <option key={w.id} value={w.id}>{w.label}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {periodKind === 'single' && mode === 'singleMonth' && (
        <div className="space-y-3">
          <p className="text-[10px] text-[var(--text-subtle)]">Pick one calendar month. No comparison.</p>
          <div>
            <label className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Month</label>
            <select
              value={singleMonthId || defaultSingleMonth}
              onChange={(e) => setSingleMonthId(e.target.value)}
              disabled={!monthOpts.length}
              className="mt-1 w-full px-2.5 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)]"
            >
              {monthOpts.map((m) => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {periodKind === 'single' && mode === 'singleQuarter' && (
        <div className="space-y-3">
          <p className="text-[10px] text-[var(--text-subtle)]">Pick one calendar quarter. No comparison.</p>
          <div>
            <label className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Quarter</label>
            <select
              value={singleQuarterId || defaultSingleQuarter}
              onChange={(e) => setSingleQuarterId(e.target.value)}
              disabled={!quarterOpts.length}
              className="mt-1 w-full px-2.5 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)]"
            >
              {quarterOpts.map((q) => (
                <option key={q.id} value={q.id}>{q.label}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      {periodKind === 'single' && mode === 'singleYear' && (
        <div className="space-y-3">
          <p className="text-[10px] text-[var(--text-subtle)]">Pick one calendar year (clipped to your data bounds). No comparison.</p>
          <div>
            <label className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Year</label>
            <select
              value={singleYearId || defaultSingleYear}
              onChange={(e) => setSingleYearId(e.target.value)}
              disabled={!yearOpts.length}
              className="mt-1 w-full px-2.5 py-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] text-xs text-[var(--text)]"
            >
              {yearOpts.map((y) => (
                <option key={y.id} value={y.id}>{y.label}</option>
              ))}
            </select>
          </div>
        </div>
      )}

      <div className="flex justify-end mt-4 gap-2">
        <button type="button" onClick={onClose} className="px-3 py-1.5 rounded-lg text-xs text-[var(--text-muted)] hover:bg-[var(--surface-2)] cursor-pointer">
          Cancel
        </button>
        <button
          type="button"
          onClick={handleApply}
          disabled={!canApply}
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-[var(--accent)] text-white text-xs font-medium hover:bg-[var(--accent-hover)] cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RotateCw size={12} /> Re-analyze
        </button>
      </div>
    </div>
  );
}
