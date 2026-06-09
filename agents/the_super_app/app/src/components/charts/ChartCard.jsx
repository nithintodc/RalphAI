import { ResponsiveContainer } from 'recharts';

/**
 * Card shell + title/subtitle + ResponsiveContainer. Standardizes the repeated
 * card/title/chart boilerplate. Pass a single recharts chart element as children.
 *
 * Props:
 *  - title, subtitle: header text (optional)
 *  - height: chart height in px (default 300)
 *  - right: optional node rendered at the right of the header (legend toggle, etc.)
 *  - className: extra classes on the card (e.g. grid spanning)
 *  - bare: render without the .card chrome (just header + chart)
 */
export default function ChartCard({
  title,
  subtitle,
  height = 300,
  right,
  className = '',
  bare = false,
  children,
}) {
  const shell = bare ? className : `card ${className}`;
  return (
    <div className={shell}>
      {(title || right) && (
        <div className="flex items-start justify-between gap-3 mb-1">
          {title && <h3 className="text-sm font-semibold text-[var(--text)]">{title}</h3>}
          {right && <div className="shrink-0">{right}</div>}
        </div>
      )}
      {subtitle && (
        <p className="text-[11px] text-[var(--text-subtle)] mb-3 leading-relaxed">{subtitle}</p>
      )}
      {!subtitle && (title || right) && <div className="mb-3" />}
      <ResponsiveContainer width="100%" height={height}>
        {children}
      </ResponsiveContainer>
    </div>
  );
}
