import { LabelList } from 'recharts';
import { barShareLabel } from '../../lib/utils/barChartShare';

/** % of series total on top of each bar (e.g. bucket orders / all orders). */
export default function BarShareLabels({ dataKey, fill = 'var(--text-muted)' }) {
  return (
    <LabelList
      dataKey={`${dataKey}_pct`}
      position="top"
      formatter={barShareLabel}
      style={{ fontSize: 9, fill, fontWeight: 600 }}
    />
  );
}
