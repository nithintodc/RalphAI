type VennCounts = {
  only_airtable: number;
  in_both: number;
  only_multilogin: number;
};

type VennSegment = "only_airtable" | "in_both" | "only_multilogin";

const SEGMENTS: {
  id: VennSegment;
  label: string;
  shortLabel: string;
  fill: string;
  stroke: string;
  text: string;
}[] = [
  {
    id: "only_airtable",
    label: "Only in Airtable",
    shortLabel: "Airtable only",
    fill: "rgba(14, 165, 233, 0.18)",
    stroke: "rgb(14, 165, 233)",
    text: "text-sky-700 dark:text-sky-300",
  },
  {
    id: "in_both",
    label: "In both",
    shortLabel: "Mapped",
    fill: "rgba(16, 185, 129, 0.22)",
    stroke: "rgb(16, 185, 129)",
    text: "text-emerald-700 dark:text-emerald-300",
  },
  {
    id: "only_multilogin",
    label: "Only in Multilogin",
    shortLabel: "Multilogin only",
    fill: "rgba(139, 92, 246, 0.18)",
    stroke: "rgb(139, 92, 246)",
    text: "text-violet-700 dark:text-violet-300",
  },
];

type Point = { x: number; y: number };

type VennGeometry = {
  cx1: number;
  cy: number;
  r1: number;
  cx2: number;
  r2: number;
  intersects: boolean;
  labels: Record<VennSegment, Point>;
  viewWidth: number;
  viewHeight: number;
  paths: Record<VennSegment, string | null>;
};

function circleArea(r: number): number {
  return Math.PI * r * r;
}

function circleIntersectionArea(r1: number, r2: number, d: number): number {
  if (d <= 0) return circleArea(Math.min(r1, r2));
  if (d >= r1 + r2) return 0;
  if (d <= Math.abs(r1 - r2)) return circleArea(Math.min(r1, r2));

  const cosA = Math.max(-1, Math.min(1, (d * d + r1 * r1 - r2 * r2) / (2 * d * r1)));
  const cosB = Math.max(-1, Math.min(1, (d * d + r2 * r2 - r1 * r1) / (2 * d * r2)));
  const a = Math.acos(cosA);
  const b = Math.acos(cosB);
  const c = 0.5 * Math.sqrt(Math.max(0, (-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2)));
  return r1 * r1 * a + r2 * r2 * b - c;
}

function circlePath(cx: number, cy: number, r: number): string {
  return `M ${cx - r} ${cy} A ${r} ${r} 0 1 0 ${cx + r} ${cy} A ${r} ${r} 0 1 0 ${cx - r} ${cy} Z`;
}

function ringPath(outerCx: number, outerCy: number, outerR: number, innerCx: number, innerCy: number, innerR: number): string {
  return `${circlePath(outerCx, outerCy, outerR)} ${circlePath(innerCx, innerCy, innerR)}`;
}

function circleIntersectionPoints(cx1: number, cy: number, r1: number, cx2: number, r2: number): [Point, Point] | null {
  const d = Math.abs(cx2 - cx1);
  if (d >= r1 + r2 || d <= Math.abs(r1 - r2)) return null;

  const a = (r1 * r1 - r2 * r2 + d * d) / (2 * d);
  const h = Math.sqrt(Math.max(0, r1 * r1 - a * a));
  const px = cx1 + a;
  const py = cy;

  return [
    { x: px, y: py - h },
    { x: px, y: py + h },
  ];
}

function arcTo(_cx: number, _cy: number, r: number, end: Point, largeArc: boolean, sweep: 0 | 1): string {
  return `A ${r} ${r} 0 ${largeArc ? 1 : 0} ${sweep} ${end.x} ${end.y}`;
}

function solveCenterDistance(r1: number, r2: number, totalA: number, totalM: number, overlap: number): number {
  if (overlap <= 0) return r1 + r2;
  if (overlap >= totalA && overlap >= totalM) return 0;
  if (overlap >= totalA) return Math.max(r2 - r1, 0);
  if (overlap >= totalM) return Math.max(r1 - r2, 0);

  const target = (overlap / totalA) * circleArea(r1);
  let lo = Math.abs(r1 - r2);
  let hi = r1 + r2;

  for (let i = 0; i < 56; i++) {
    const mid = (lo + hi) / 2;
    const area = circleIntersectionArea(r1, r2, mid);
    if (area < target) hi = mid;
    else lo = mid;
  }

  return (lo + hi) / 2;
}

function crescentLabel(cx: number, cy: number, r: number, toward: "left" | "right"): Point {
  const offset = Math.max(r * 0.4, 12);
  return { x: cx + (toward === "left" ? -offset : offset), y: cy };
}

function buildRegionPaths(
  cx1: number,
  cy: number,
  r1: number,
  cx2: number,
  r2: number,
  counts: VennCounts,
): Record<VennSegment, string | null> {
  const d = cx2 - cx1;
  const pts = circleIntersectionPoints(cx1, cy, r1, cx2, r2);

  if (counts.in_both <= 0) {
    return {
      only_airtable: counts.only_airtable > 0 ? circlePath(cx1, cy, r1) : null,
      in_both: null,
      only_multilogin: counts.only_multilogin > 0 ? circlePath(cx2, cy, r2) : null,
    };
  }

  if (!pts) {
    const nested = d <= Math.abs(r1 - r2);
    if (nested && r1 <= r2) {
      return {
        only_airtable: null,
        in_both: counts.in_both > 0 ? circlePath(cx1, cy, r1) : null,
        only_multilogin:
          counts.only_multilogin > 0 ? ringPath(cx2, cy, r2, cx1, cy, r1) : null,
      };
    }
    if (nested && r2 < r1) {
      return {
        only_airtable:
          counts.only_airtable > 0 ? ringPath(cx1, cy, r1, cx2, cy, r2) : null,
        in_both: counts.in_both > 0 ? circlePath(cx2, cy, r2) : null,
        only_multilogin: null,
      };
    }
    return {
      only_airtable: counts.only_airtable > 0 ? circlePath(cx1, cy, r1) : null,
      in_both: null,
      only_multilogin: counts.only_multilogin > 0 ? circlePath(cx2, cy, r2) : null,
    };
  }

  const [top, bottom] = pts;
  const leftOuterLarge = d < r2;
  const rightOuterLarge = d < r1;

  return {
    only_airtable:
      counts.only_airtable > 0
        ? [`M ${top.x} ${top.y}`, arcTo(cx1, cy, r1, bottom, !leftOuterLarge, 1), arcTo(cx2, cy, r2, top, rightOuterLarge, 0), "Z"].join(" ")
        : null,
    in_both: [`M ${top.x} ${top.y}`, arcTo(cx2, cy, r2, bottom, !rightOuterLarge, 1), arcTo(cx1, cy, r1, top, leftOuterLarge, 0), "Z"].join(" "),
    only_multilogin:
      counts.only_multilogin > 0
        ? [`M ${top.x} ${top.y}`, arcTo(cx2, cy, r2, bottom, rightOuterLarge, 0), arcTo(cx1, cy, r1, top, leftOuterLarge, 1), "Z"].join(" ")
        : null,
  };
}

function computeVennGeometry(counts: VennCounts): VennGeometry {
  const totalA = counts.only_airtable + counts.in_both;
  const totalM = counts.only_multilogin + counts.in_both;
  const padding = 40;
  const maxRadius = 105;

  if (totalA === 0 && totalM === 0) {
    const cx = 200;
    const cy = 120;
    return {
      cx1: cx,
      cy,
      r1: 0,
      cx2: cx,
      r2: 0,
      intersects: false,
      labels: {
        only_airtable: { x: cx, y: cy },
        in_both: { x: cx, y: cy },
        only_multilogin: { x: cx, y: cy },
      },
      viewWidth: 400,
      viewHeight: 240,
      paths: { only_airtable: null, in_both: null, only_multilogin: null },
    };
  }

  const dominant = Math.max(totalA, totalM, 1);
  const scale = maxRadius / Math.sqrt(dominant);
  const r1 = Math.sqrt(totalA) * scale;
  const r2 = Math.sqrt(totalM) * scale;
  const d = solveCenterDistance(r1, r2, totalA, totalM, counts.in_both);

  const cx1 = 0;
  const cx2 = d;
  const cy = 0;
  const minX = Math.min(cx1 - r1, cx2 - r2);
  const maxX = Math.max(cx1 + r1, cx2 + r2);
  const maxR = Math.max(r1, r2);
  const offsetX = padding - minX;
  const offsetY = padding + maxR;

  const shifted = {
    cx1: cx1 + offsetX,
    cy: cy + offsetY,
    r1,
    cx2: cx2 + offsetX,
    r2,
  };

  const intersects = counts.in_both > 0 && d < r1 + r2;
  const airtableInsideMultilogin = counts.in_both >= totalA && totalA > 0 && r1 <= r2;
  const multiloginInsideAirtable = counts.in_both >= totalM && totalM > 0 && r2 < r1;

  let inBothLabel = { x: (shifted.cx1 + shifted.cx2) / 2, y: shifted.cy };
  let onlyMultiloginLabel = crescentLabel(shifted.cx2, shifted.cy, r2, "right");
  let onlyAirtableLabel = crescentLabel(shifted.cx1, shifted.cy, r1, "left");

  if (airtableInsideMultilogin) {
    inBothLabel = { x: shifted.cx1, y: shifted.cy };
    onlyMultiloginLabel = {
      x: shifted.cx2 + Math.max((r2 - r1) * 0.45 + r1 * 0.35, 18),
      y: shifted.cy,
    };
    onlyAirtableLabel = { x: shifted.cx1 - r1 * 0.55, y: shifted.cy };
  } else if (multiloginInsideAirtable) {
    inBothLabel = { x: shifted.cx2, y: shifted.cy };
    onlyAirtableLabel = {
      x: shifted.cx1 - Math.max((r1 - r2) * 0.45 + r2 * 0.35, 18),
      y: shifted.cy,
    };
  }

  return {
    ...shifted,
    intersects,
    labels: {
      only_airtable: onlyAirtableLabel,
      in_both: inBothLabel,
      only_multilogin: onlyMultiloginLabel,
    },
    viewWidth: maxX - minX + padding * 2,
    viewHeight: maxR * 2 + padding * 2,
    paths: buildRegionPaths(shifted.cx1, shifted.cy, r1, shifted.cx2, r2, counts),
  };
}

export function OperatorMappingVenn({
  counts,
  active,
  onSelect,
}: {
  counts: VennCounts;
  active: VennSegment | null;
  onSelect: (segment: VennSegment) => void;
}) {
  const total = counts.only_airtable + counts.in_both + counts.only_multilogin || 1;
  const geom = computeVennGeometry(counts);

  const segmentFills: Record<VennSegment, string> = {
    only_airtable: active === "only_airtable" ? "rgba(14,165,233,0.32)" : "rgba(14,165,233,0.14)",
    in_both: active === "in_both" ? "rgba(16,185,129,0.38)" : "rgba(16,185,129,0.2)",
    only_multilogin: active === "only_multilogin" ? "rgba(139,92,246,0.32)" : "rgba(139,92,246,0.14)",
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
      <div className="relative mx-auto w-full max-w-xl">
        <svg
          viewBox={`0 0 ${geom.viewWidth} ${geom.viewHeight}`}
          className="h-auto w-full"
          role="img"
          aria-label="Operator mapping Venn diagram with areas proportional to counts"
        >
          {geom.r1 > 0 && (
            <circle
              cx={geom.cx1}
              cy={geom.cy}
              r={geom.r1}
              fill="rgba(14, 165, 233, 0.06)"
              stroke="rgb(14, 165, 233)"
              strokeWidth="2"
              pointerEvents="none"
            />
          )}
          {geom.r2 > 0 && (
            <circle
              cx={geom.cx2}
              cy={geom.cy}
              r={geom.r2}
              fill="rgba(139, 92, 246, 0.06)"
              stroke="rgb(139, 92, 246)"
              strokeWidth="2"
              pointerEvents="none"
            />
          )}

          {SEGMENTS.map((seg) => {
            const path = geom.paths[seg.id];
            if (!path) return null;
            const isRing = path.includes(" Z M ");
            return (
              <path
                key={seg.id}
                d={path}
                fill={segmentFills[seg.id]}
                fillRule={isRing ? "evenodd" : "nonzero"}
                stroke={seg.stroke}
                strokeWidth={active === seg.id ? 2.5 : 1.5}
                className="cursor-pointer transition-colors"
                onClick={() => onSelect(seg.id)}
              />
            );
          })}

          {geom.r1 > 0 && (
            <text
              x={geom.cx1}
              y={geom.cy - geom.r1 - 12}
              textAnchor="middle"
              className="fill-sky-700 text-[13px] font-semibold dark:fill-sky-300"
            >
              Airtable ({counts.only_airtable + counts.in_both})
            </text>
          )}
          {geom.r2 > 0 && (
            <text
              x={geom.cx2}
              y={geom.cy - geom.r2 - 12}
              textAnchor="middle"
              className="fill-violet-700 text-[13px] font-semibold dark:fill-violet-300"
            >
              Multilogin ({counts.only_multilogin + counts.in_both})
            </text>
          )}

          <text
            x={geom.labels.only_airtable.x}
            y={geom.labels.only_airtable.y - 6}
            textAnchor="middle"
            className="fill-sky-800 text-[20px] font-bold dark:fill-sky-200"
          >
            {counts.only_airtable}
          </text>
          <text
            x={geom.labels.only_airtable.x}
            y={geom.labels.only_airtable.y + 14}
            textAnchor="middle"
            className="fill-sky-600 text-[11px] dark:fill-sky-400"
          >
            only Airtable
          </text>

          {geom.intersects && (
            <>
              <text
                x={geom.labels.in_both.x}
                y={geom.labels.in_both.y - 6}
                textAnchor="middle"
                className="fill-emerald-800 text-[20px] font-bold dark:fill-emerald-200"
              >
                {counts.in_both}
              </text>
              <text
                x={geom.labels.in_both.x}
                y={geom.labels.in_both.y + 14}
                textAnchor="middle"
                className="fill-emerald-600 text-[11px] dark:fill-emerald-400"
              >
                both
              </text>
            </>
          )}

          <text
            x={geom.labels.only_multilogin.x}
            y={geom.labels.only_multilogin.y - 6}
            textAnchor="middle"
            className="fill-violet-800 text-[20px] font-bold dark:fill-violet-200"
          >
            {counts.only_multilogin}
          </text>
          <text
            x={geom.labels.only_multilogin.x}
            y={geom.labels.only_multilogin.y + 14}
            textAnchor="middle"
            className="fill-violet-600 text-[11px] dark:fill-violet-400"
          >
            only Multilogin
          </text>
        </svg>
        <p className="mt-2 text-center text-xs text-ink-500 dark:text-white/50">
          Circle areas match set totals; overlap size matches mapped count.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {SEGMENTS.map((seg) => {
          const count = counts[seg.id];
          const pct = Math.round((count / total) * 100);
          const isActive = active === seg.id;
          return (
            <button
              key={seg.id}
              type="button"
              onClick={() => onSelect(seg.id)}
              className={`rounded-2xl border p-4 text-left transition ${
                isActive
                  ? "border-brand-400 bg-brand-50 shadow-sm dark:border-brand-500/50 dark:bg-brand-500/10"
                  : "border-brand-100 bg-white hover:bg-brand-50/60 dark:border-white/10 dark:bg-white/5 dark:hover:bg-white/10"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className={`text-sm font-semibold ${seg.text}`}>{seg.label}</p>
                  <p className="mt-0.5 text-xs text-ink-500 dark:text-white/55">{seg.shortLabel}</p>
                </div>
                <div className="text-right">
                  <p className="font-display text-2xl font-semibold text-ink-900 dark:text-white">{count}</p>
                  <p className="text-xs text-ink-500 dark:text-white/50">{pct}%</p>
                </div>
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-brand-100 dark:bg-white/10">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: seg.stroke,
                  }}
                />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export type { VennSegment };
