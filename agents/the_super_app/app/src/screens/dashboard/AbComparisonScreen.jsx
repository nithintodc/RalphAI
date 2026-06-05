import { useMemo, useState } from 'react';
import { Download } from 'lucide-react';
import { useDataStore } from '../../stores/dataStore';
import { useConfigStore } from '../../stores/configStore';
import SplitDataTable from '../../components/ui/SplitDataTable';
import { fmt, formatByKind } from '../../lib/utils/formatters';
import { formatStoreTagLabel } from '../../lib/export/exportSheetSummaries';
import { buildAbComparison, buildSingleTagComparison, getUniqueStoreTags, STORE_GROWTH_SPECS } from '../../lib/engine/abComparison';
import { exportAbReport } from '../../lib/export/exportAbWorkbook';

function tagLabel(tag) {
  return formatStoreTagLabel(tag) || tag;
}

function renderMetric(kind, v) {
  return formatByKind(kind, v);
}

function SectionHeader({ title, subtitle }) {
  return (
    <div className="mb-2">
      <h3 className="text-sm font-semibold text-[var(--text)]">{title}</h3>
      {subtitle && <p className="text-[11px] text-[var(--text-subtle)] mt-0.5 leading-relaxed">{subtitle}</p>}
    </div>
  );
}

function GroupPrePostTable({ title, subtitle, rows }) {
  if (!rows?.length) return null;
  const columns = [
    { key: 'metric', label: 'Metric', sortable: false, wrap: true },
    { key: 'pre', label: 'Pre', align: 'right', wrap: true, render: (v, r) => renderMetric(r.kind, v) },
    { key: 'post', label: 'Post', align: 'right', wrap: true, render: (v, r) => renderMetric(r.kind, v) },
    { key: 'prevspost', label: 'Pre vs Post', align: 'right', wrap: true, render: (v, r) => renderMetric(r.kind, v) },
    { key: 'lyPrevspost', label: 'LY Pre vs Post', align: 'right', wrap: true, render: (v, r) => renderMetric(r.kind, v) },
    { key: 'growthPct', label: 'Growth%', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'lyGrowthPct', label: 'LY Growth%', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
  ];
  return (
    <div className="card">
      <SectionHeader title={title} subtitle={subtitle} />
      <SplitDataTable columns={columns} data={rows} sortable={false} dense />
    </div>
  );
}

function GroupYoyTable({ title, subtitle, rows }) {
  if (!rows?.length) return null;
  const columns = [
    { key: 'metric', label: 'Metric', sortable: false, wrap: true },
    { key: 'postLY', label: 'LY Post', align: 'right', wrap: true, render: (v, r) => renderMetric(r.kind, v) },
    { key: 'post', label: 'Post', align: 'right', wrap: true, render: (v, r) => renderMetric(r.kind, v) },
    { key: 'yoy', label: 'YoY', align: 'right', wrap: true, render: (v, r) => renderMetric(r.kind, v) },
    { key: 'yoyPct', label: 'YoY%', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
  ];
  return (
    <div className="card">
      <SectionHeader title={title} subtitle={subtitle} />
      <SplitDataTable columns={columns} data={rows} sortable={false} dense />
    </div>
  );
}

function GroupGrowthProfileTable({ title, subtitle, rows }) {
  if (!rows?.length) return null;
  const columns = [
    { key: 'metric', label: 'Metric', sortable: false, wrap: true },
    { key: 'pvpPct', label: 'PvP%', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'lyPvpPct', label: 'LY PvP%', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'yoyPct', label: 'YoY%', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
  ];
  return (
    <div className="card">
      <SectionHeader title={title} subtitle={subtitle} />
      <SplitDataTable columns={columns} data={rows} sortable={false} dense />
    </div>
  );
}

function FocusedGrowthTable({ title, subtitle, leftTag, rightTag, rows }) {
  if (!rows?.length) return null;
  const columns = [
    { key: 'metric', label: 'Metric', sortable: false, wrap: true },
    { key: 'leftPct', label: `${leftTag} %`, align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'rightPct', label: `${rightTag} %`, align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'gap', label: 'Gap (pp)', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
  ];
  return (
    <div className="card">
      <SectionHeader title={title} subtitle={subtitle} />
      <SplitDataTable columns={columns} data={rows} sortable={false} dense />
    </div>
  );
}

function HeadlineGrowthTable({ title, subtitle, leftTag, rightTag, rows }) {
  if (!rows?.length) return null;
  const columns = [
    { key: 'metric', label: 'Metric', sortable: false, wrap: true },
    { key: 'leftPvpPct', label: `${leftTag} PvP%`, align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'rightPvpPct', label: `${rightTag} PvP%`, align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'pvpGap', label: 'PvP Gap', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'leftYoyPct', label: `${leftTag} YoY%`, align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'rightYoyPct', label: `${rightTag} YoY%`, align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'yoyGap', label: 'YoY Gap', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'leftLyPvpPct', label: `${leftTag} LY PvP%`, align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'rightLyPvpPct', label: `${rightTag} LY PvP%`, align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'lyPvpGap', label: 'LY PvP Gap', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
  ];
  return (
    <div className="card border-[var(--accent-border)] bg-[var(--accent-soft)]/30">
      <SectionHeader title={title} subtitle={subtitle} />
      <SplitDataTable columns={columns} data={rows} sortable={false} dense />
    </div>
  );
}

function DistributionTable({ title, subtitle, leftTag, rightTag, rows }) {
  if (!rows?.length) return null;
  const columns = [
    { key: 'metric', label: 'Metric', sortable: false, wrap: true },
    { key: 'growthType', label: 'Growth', sortable: false, wrap: true },
    { key: 'leftMedian', label: `${leftTag} median%`, align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'rightMedian', label: `${rightTag} median%`, align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'medianGap', label: 'Median gap', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'leftAvg', label: `${leftTag} avg%`, align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'rightAvg', label: `${rightTag} avg%`, align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'avgGap', label: 'Avg gap', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'leftPositiveRate', label: `${leftTag} % +ve`, align: 'right', wrap: true, render: (v) => fmt.pct(v) },
    { key: 'rightPositiveRate', label: `${rightTag} % +ve`, align: 'right', wrap: true, render: (v) => fmt.pct(v) },
    { key: 'positiveRateGap', label: '+ve gap', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
  ];
  return (
    <div className="card">
      <SectionHeader title={title} subtitle={subtitle} />
      <SplitDataTable columns={columns} data={rows} sortable={false} dense />
    </div>
  );
}

function OutperformanceTable({ title, subtitle, rows }) {
  if (!rows?.length) return null;
  const columns = [
    { key: 'metric', label: 'Metric', sortable: false, wrap: true },
    { key: 'growthType', label: 'Growth', sortable: false, wrap: true },
    { key: 'medianWinner', label: 'Median winner', sortable: false, wrap: true },
    { key: 'avgWinner', label: 'Avg winner', sortable: false, wrap: true },
    { key: 'positiveWinner', label: '% +ve winner', sortable: false, wrap: true },
    { key: 'medianGap', label: 'Median gap', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'avgGap', label: 'Avg gap', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
    { key: 'positiveRateGap', label: '+ve gap', align: 'right', delta: true, wrap: true, render: (v) => fmt.delta(v) },
  ];
  return (
    <div className="card">
      <SectionHeader title={title} subtitle={subtitle} />
      <SplitDataTable columns={columns} data={rows} sortable={false} dense />
    </div>
  );
}

function StorePctTable({ title, subtitle, rows }) {
  if (!rows?.length) return null;
  const columns = [
    { key: 'tag', label: 'Tag', sortable: true, wrap: true },
    { key: 'storeId', label: 'Store', sortable: true, wrap: true },
    ...STORE_GROWTH_SPECS.flatMap((spec) => ([
      { key: `${spec.key}_pvp`, label: `${spec.label} PvP%`, align: 'right', sortable: true, delta: true, wrap: true, render: (v) => fmt.delta(v) },
      { key: `${spec.key}_yoy`, label: `${spec.label} YoY%`, align: 'right', sortable: true, delta: true, wrap: true, render: (v) => fmt.delta(v) },
    ])),
  ];
  return (
    <div className="card">
      <SectionHeader title={title} subtitle={subtitle} />
      <SplitDataTable columns={columns} data={rows} maxHeight="480px" dense />
    </div>
  );
}

export default function AbComparisonScreen() {
  const combined = useDataStore((s) => s.storeTables?.combined || []);
  const tagMap = useConfigStore((s) => s.storeTagMap || {});
  const abGroupFilter = useConfigStore((s) => s.abGroupFilter || 'all');
  const [leftTag, setLeftTag] = useState('A');
  const [rightTag, setRightTag] = useState('B');
  const [exporting, setExporting] = useState(false);
  const [exportMsg, setExportMsg] = useState('');

  const tags = useMemo(() => getUniqueStoreTags(tagMap), [tagMap]);

  const comparison = useMemo(
    () => buildAbComparison(combined, tagMap, leftTag, rightTag),
    [combined, tagMap, leftTag, rightTag],
  );

  const singleGroup = useMemo(() => {
    if (abGroupFilter !== 'A' && abGroupFilter !== 'B') return null;
    return buildSingleTagComparison(combined, tagMap, abGroupFilter);
  }, [combined, tagMap, abGroupFilter]);

  const taggedCounts = useMemo(() => {
    const out = {};
    for (const t of Object.values(tagMap)) {
      const key = String(t || '').trim();
      if (!key) continue;
      out[key] = (out[key] || 0) + 1;
    }
    return out;
  }, [tagMap]);

  const handleAbExport = async () => {
    if (exporting) return;
    setExporting(true);
    setExportMsg('');
    try {
      const data = useDataStore.getState();
      const config = useConfigStore.getState();
      const result = exportAbReport(data, config, { leftTag, rightTag });
      setExportMsg(`Exported ${result.filename}`);
    } catch (err) {
      setExportMsg(err.message || String(err));
    } finally {
      setExporting(false);
    }
  };

  if (!tags.length) {
    return <div className="card text-sm text-[var(--text-muted)]">No store tags found. Add Tag values in Config → store map first.</div>;
  }

  const exportButton = (
    <button
      type="button"
      onClick={handleAbExport}
      disabled={exporting}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--accent-border)] bg-[var(--accent-soft)] text-xs font-medium text-[var(--accent-text)] hover:bg-[var(--accent-soft)] cursor-pointer disabled:opacity-60"
    >
      <Download size={13} />
      {exporting ? 'Exporting…' : 'A/B Export'}
    </button>
  );

  if (abGroupFilter === 'A' || abGroupFilter === 'B') {
    const g = singleGroup;
    return (
      <div className="space-y-4">
        <div className="card flex flex-wrap items-center gap-3">
          <div className="text-xs text-[var(--text-muted)]">
            Showing <strong>{tagLabel(abGroupFilter)}</strong> only ({g?.storeCount || 0} stores). Change scope in the top bar.
          </div>
          <div className="ml-auto flex items-center gap-2">
            {exportButton}
            {exportMsg && <span className="text-[11px] text-[var(--text-subtle)]">{exportMsg}</span>}
          </div>
        </div>
        <GroupGrowthProfileTable
          title={`${tagLabel(abGroupFilter)} — Growth profile`}
          subtitle="Aggregated growth rates for this cohort."
          rows={g?.growthProfileRows}
        />
        <GroupPrePostTable title={`${tagLabel(abGroupFilter)} — Pre vs Post`} rows={g?.prePostRows} />
        <GroupYoyTable title={`${tagLabel(abGroupFilter)} — Year over Year`} rows={g?.yoyRows} />
        <StorePctTable
          title={`${tagLabel(abGroupFilter)} — Store-level growth rates`}
          subtitle="Per-store growth % — comparable across stores within the group."
          rows={g?.storeLevelPctRows}
        />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="card flex flex-wrap items-center gap-3">
        <div className="text-xs text-[var(--text-muted)]">Compare groups</div>
        <select value={leftTag} onChange={(e) => setLeftTag(e.target.value)} className="px-2 py-1 rounded border border-[var(--border)] bg-[var(--surface)] text-xs">
          {tags.map((t) => <option key={`l-${t}`} value={t}>{t === 'A' || t === 'B' ? `${t} (${tagLabel(t)})` : t}</option>)}
        </select>
        <span className="text-xs text-[var(--text-subtle)]">vs</span>
        <select value={rightTag} onChange={(e) => setRightTag(e.target.value)} className="px-2 py-1 rounded border border-[var(--border)] bg-[var(--surface)] text-xs">
          {tags.map((t) => <option key={`r-${t}`} value={t}>{t === 'A' || t === 'B' ? `${t} (${tagLabel(t)})` : t}</option>)}
        </select>
        <span className="text-xs text-[var(--text-subtle)]">
          {tagLabel(leftTag)}: {taggedCounts[leftTag] || 0} ({comparison.leftStoreCount} in analysis) · {tagLabel(rightTag)}: {taggedCounts[rightTag] || 0} ({comparison.rightStoreCount} in analysis)
        </span>
        <div className="ml-auto flex items-center gap-2">
          {exportButton}
          {exportMsg && <span className="text-[11px] text-[var(--text-subtle)]">{exportMsg}</span>}
        </div>
      </div>

      <div className="card text-[11px] text-[var(--text-muted)] leading-relaxed border-amber-200 bg-amber-50/60">
        <strong>Strategist view:</strong> Groups have unequal store counts ({comparison.leftStoreCount} vs {comparison.rightStoreCount}).
        Cross-group comparisons below use <strong>growth % only</strong> — never absolute Pre/Post totals.
        Within-group tables include absolutes for cohort context.
      </div>

      <div className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-subtle)]">Within-group context</p>
        <div className="grid gap-4 lg:grid-cols-2">
          <GroupGrowthProfileTable
            title={`${tagLabel(leftTag)} — Growth profile`}
            subtitle="Headline growth rates for this cohort."
            rows={comparison.leftGrowthProfileRows}
          />
          <GroupGrowthProfileTable
            title={`${tagLabel(rightTag)} — Growth profile`}
            subtitle="Headline growth rates for this cohort."
            rows={comparison.rightGrowthProfileRows}
          />
        </div>
        <GroupPrePostTable
          title={`${tagLabel(leftTag)} — Pre vs Post`}
          subtitle="Internal cohort view — absolutes shown for context."
          rows={comparison.leftPrePostRows}
        />
        <GroupPrePostTable
          title={`${tagLabel(rightTag)} — Pre vs Post`}
          subtitle="Internal cohort view — absolutes shown for context."
          rows={comparison.rightPrePostRows}
        />
        <GroupYoyTable title={`${tagLabel(leftTag)} — Year over Year`} rows={comparison.leftYoyRows} />
        <GroupYoyTable title={`${tagLabel(rightTag)} — Year over Year`} rows={comparison.rightYoyRows} />
      </div>

      <div className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-subtle)]">Cross-group comparison (% only)</p>
        <HeadlineGrowthTable
          title={`${tagLabel(leftTag)} vs ${tagLabel(rightTag)} — Headline growth % comparison`}
          subtitle="All metrics: PvP%, YoY%, and LY PvP% with gap (percentage points)."
          leftTag={leftTag}
          rightTag={rightTag}
          rows={comparison.growthComparisonRows}
        />
        <div className="grid gap-4 lg:grid-cols-3">
          <FocusedGrowthTable
            title="Pre vs Post growth %"
            subtitle="Which group grew faster this period?"
            leftTag={leftTag}
            rightTag={rightTag}
            rows={comparison.pvpComparisonRows}
          />
          <FocusedGrowthTable
            title="YoY growth %"
            subtitle="Which group is beating last year?"
            leftTag={leftTag}
            rightTag={rightTag}
            rows={comparison.yoyComparisonRows}
          />
          <FocusedGrowthTable
            title="LY Pre vs Post growth %"
            subtitle="Baseline trend comparison."
            leftTag={leftTag}
            rightTag={rightTag}
            rows={comparison.lyPvpComparisonRows}
          />
        </div>
      </div>

      <div className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-subtle)]">Store-level distribution</p>
        <DistributionTable
          title={`${tagLabel(leftTag)} vs ${tagLabel(rightTag)} — Growth rate distribution`}
          subtitle="Median, average, and % of stores with positive growth — fair comparison across unequal cohorts."
          leftTag={leftTag}
          rightTag={rightTag}
          rows={comparison.distributionRows}
        />
        <OutperformanceTable
          title={`${tagLabel(leftTag)} vs ${tagLabel(rightTag)} — Outperformance scorecard`}
          subtitle="Which group wins on median, average, and breadth of positive growth."
          rows={comparison.outperformanceRows}
        />
        <StorePctTable
          title={`${tagLabel(leftTag)} vs ${tagLabel(rightTag)} — Store-level growth rates`}
          subtitle="Every store's growth % — no absolute values. Sort to find outliers."
          rows={comparison.storeLevelPctRows}
        />
      </div>
    </div>
  );
}
