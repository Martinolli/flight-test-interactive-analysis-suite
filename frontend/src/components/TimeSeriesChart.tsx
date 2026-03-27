import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { ParameterSeries } from '../services/api';

// Palette for up to 8 overlaid series
const COLORS = [
  '#2563eb', // blue-600
  '#16a34a', // green-600
  '#ea580c', // orange-600
  '#9333ea', // purple-600
  '#dc2626', // red-600
  '#0891b2', // cyan-600
  '#d97706', // amber-600
  '#db2777', // pink-600
];

interface TimeSeriesChartProps {
  series: ParameterSeries[];
  height?: number;
  showReferenceMean?: boolean;
}

interface MergedPoint {
  time: string;
  [key: string]: string | number;
}

/**
 * Merges multiple ParameterSeries arrays into a single array of objects
 * keyed by ISO timestamp, suitable for Recharts multi-line rendering.
 */
function mergeSeries(series: ParameterSeries[]): MergedPoint[] {
  const map = new Map<string, MergedPoint>();

  series.forEach((s) => {
    s.data.forEach((pt) => {
      const existing = map.get(pt.timestamp) ?? { time: pt.timestamp };
      existing[s.parameter_name] = pt.value;
      map.set(pt.timestamp, existing);
    });
  });

  return Array.from(map.values()).sort((a, b) =>
    new Date(a.time).getTime() - new Date(b.time).getTime()
  );
}

function formatTimestamp(ts: string): string {
  const d = new Date(ts);
  // If the date is valid, show HH:MM:SS; otherwise show raw string
  if (isNaN(d.getTime())) return ts;
  return d.toLocaleTimeString('en-US', { hour12: false });
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string; unit?: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-sm min-w-[160px]">
      <p className="text-gray-500 text-xs mb-2">{label ? formatTimestamp(label) : ''}</p>
      {payload.map((entry) => (
        <div key={entry.name} className="flex items-center justify-between gap-4 py-0.5">
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
              style={{ backgroundColor: entry.color }}
            />
            <span className="text-gray-700 truncate max-w-[100px]">{entry.name}</span>
          </span>
          <span className="font-semibold text-gray-900">
            {typeof entry.value === 'number'
              ? entry.value.toLocaleString(undefined, { maximumFractionDigits: 4 })
              : entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function TimeSeriesChart({
  series,
  height = 320,
  showReferenceMean = false,
}: TimeSeriesChartProps) {
  if (!series.length) return null;

  const data = mergeSeries(series);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey="time"
          tickFormatter={formatTimestamp}
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          axisLine={{ stroke: '#e5e7eb' }}
          tickLine={false}
          minTickGap={60}
        />
        <YAxis
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          axisLine={false}
          tickLine={false}
          width={52}
          tickFormatter={(v: number) =>
            v.toLocaleString(undefined, { maximumFractionDigits: 2 })
          }
        />
        <Tooltip content={<CustomTooltip />} />
        {series.length > 1 && (
          <Legend
            wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
            iconType="circle"
            iconSize={8}
          />
        )}

        {series.map((s, i) => (
          <Line
            key={s.parameter_name}
            type="monotone"
            dataKey={s.parameter_name}
            stroke={COLORS[i % COLORS.length]}
            strokeWidth={2}
            dot={data.length <= 100}
            activeDot={{ r: 4 }}
            connectNulls
          />
        ))}

        {showReferenceMean &&
          series.map((s, i) => (
            <ReferenceLine
              key={`mean-${s.parameter_name}`}
              y={s.statistics.mean}
              stroke={COLORS[i % COLORS.length]}
              strokeDasharray="6 3"
              strokeOpacity={0.5}
              label={{
                value: `μ ${s.statistics.mean.toFixed(2)}`,
                position: 'insideTopRight',
                fontSize: 10,
                fill: COLORS[i % COLORS.length],
              }}
            />
          ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
