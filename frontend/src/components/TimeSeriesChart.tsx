import {
  ComposedChart,
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
  syncId?: string;
  onHoverPoint?: (snapshot: TimeSeriesHoverSnapshot | null) => void;
}

interface MergedPoint {
  time: string;
  [key: string]: string | number;
}

export interface TimeSeriesHoverSnapshot {
  timestamp: string;
  values: Record<string, number>;
}

/**
 * Groups series by unit so we can assign them to left or right Y-axis.
 *
 * Rules:
 *  - First distinct unit group  → left  axis  (yAxisId="left")
 *  - Second distinct unit group → right axis  (yAxisId="right")
 *  - If all series share the same unit, only the left axis is rendered.
 *  - Beyond two distinct unit groups we still render correctly — the third+
 *    group falls back to the right axis (same scale grouping as group 2).
 */
/**
 * Detect if a series is a binary (0/1) signal — all values are 0 or 1.
 * These need special Y-axis treatment so zeros are visible.
 */
function isBinarySeries(s: ParameterSeries): boolean {
  if (!s.data.length) return false;
  return s.data.every((pt) => pt.value === 0 || pt.value === 1);
}

function groupByUnit(series: ParameterSeries[]): {
  leftSeries: ParameterSeries[];
  rightSeries: ParameterSeries[];
  leftUnit: string;
  rightUnit: string;
} {
  const unitOrder: string[] = [];
  const unitMap = new Map<string, ParameterSeries[]>();

  series.forEach((s) => {
    const unit = s.unit ?? 'value';
    if (!unitMap.has(unit)) {
      unitOrder.push(unit);
      unitMap.set(unit, []);
    }
    unitMap.get(unit)!.push(s);
  });

  const leftUnit = unitOrder[0] ?? 'value';
  const rightUnit = unitOrder[1] ?? '';

  const leftSeries = unitMap.get(leftUnit) ?? [];
  // All remaining unit groups go to the right axis
  const rightSeries = unitOrder
    .slice(1)
    .flatMap((u) => unitMap.get(u) ?? []);

  return { leftSeries, rightSeries, leftUnit, rightUnit };
}

function mergeSeries(series: ParameterSeries[]): MergedPoint[] {
  const map = new Map<string, MergedPoint>();

  series.forEach((s) => {
    s.data.forEach((pt) => {
      const existing = map.get(pt.timestamp) ?? { time: pt.timestamp };
      existing[s.parameter_name] = pt.value;
      map.set(pt.timestamp, existing);
    });
  });

  return Array.from(map.values()).sort(
    (a, b) => new Date(a.time).getTime() - new Date(b.time).getTime()
  );
}

function formatTimestamp(ts: string): string {
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  return d.toLocaleTimeString('en-US', { hour12: false });
}

// ── Custom Tooltip ──────────────────────────────────────────────────────────
function CustomTooltip({
  active,
  payload,
  label,
  seriesMeta,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
  seriesMeta: Map<string, { unit: string; axis: 'left' | 'right' }>;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-sm min-w-[180px]">
      <p className="text-gray-500 text-xs mb-2 font-medium">
        {label ? formatTimestamp(label) : ''}
      </p>
      {payload.map((entry) => {
        const meta = seriesMeta.get(entry.name);
        return (
          <div
            key={entry.name}
            className="flex items-center justify-between gap-4 py-0.5"
          >
            <span className="flex items-center gap-1.5 min-w-0">
              <span
                className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
                style={{ backgroundColor: entry.color }}
              />
              <span className="text-gray-700 truncate max-w-[120px]">
                {entry.name}
              </span>
            </span>
            <span className="font-semibold text-gray-900 shrink-0">
              {typeof entry.value === 'number'
                ? entry.value.toLocaleString(undefined, {
                    maximumFractionDigits: 4,
                  })
                : entry.value}
              {meta?.unit ? (
                <span className="text-gray-400 font-normal ml-1 text-xs">
                  {meta.unit}
                </span>
              ) : null}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ── Custom Legend ────────────────────────────────────────────────────────────
function CustomLegend({
  payload,
  seriesMeta,
}: {
  payload?: { value: string; color: string }[];
  seriesMeta: Map<string, { unit: string; axis: 'left' | 'right' }>;
}) {
  if (!payload?.length) return null;
  return (
    <div className="flex flex-wrap justify-center gap-x-5 gap-y-1 pt-2">
      {payload.map((entry) => {
        const meta = seriesMeta.get(entry.value);
        return (
          <span
            key={entry.value}
            className="flex items-center gap-1.5 text-xs text-gray-600"
          >
            <span
              className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
              style={{ backgroundColor: entry.color }}
            />
            {entry.value}
            {meta?.unit ? (
              <span className="text-gray-400">({meta.unit})</span>
            ) : null}
            {meta?.axis === 'right' ? (
              <span className="text-gray-400 italic text-[10px]">→ right</span>
            ) : null}
          </span>
        );
      })}
    </div>
  );
}

// ── Main component ───────────────────────────────────────────────────────────
export default function TimeSeriesChart({
  series,
  height = 340,
  showReferenceMean = false,
  syncId,
  onHoverPoint,
}: TimeSeriesChartProps) {
  if (!series.length) return null;

  const { leftSeries, rightSeries, leftUnit, rightUnit } = groupByUnit(series);
  const hasDualAxis = rightSeries.length > 0;
  const data = mergeSeries(series);

  // Build a lookup map for tooltip / legend enrichment
  const seriesMeta = new Map<string, { unit: string; axis: 'left' | 'right' }>();
  leftSeries.forEach((s) =>
    seriesMeta.set(s.parameter_name, { unit: s.unit ?? '', axis: 'left' })
  );
  rightSeries.forEach((s) =>
    seriesMeta.set(s.parameter_name, { unit: s.unit ?? '', axis: 'right' })
  );

  // Global color index so colors are consistent regardless of axis assignment
  const colorIndex = new Map<string, number>();
  series.forEach((s, i) => colorIndex.set(s.parameter_name, i));

  // Binary series detection — used to adjust Y-axis domain and line type
  const binaryNames = new Set(series.filter(isBinarySeries).map((s) => s.parameter_name));
  const leftHasBinary = leftSeries.some((s) => binaryNames.has(s.parameter_name));
  const rightHasBinary = rightSeries.some((s) => binaryNames.has(s.parameter_name));

  const rightMargin = hasDualAxis ? 64 : 16;

  return (
    <div>
      {hasDualAxis && (
        <div className="flex items-center justify-end gap-6 mb-1 pr-2 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-0.5 bg-gray-400" />
            Left axis:{' '}
            <strong className="text-gray-700 ml-1">{leftUnit}</strong>
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-0.5 bg-gray-400" />
            Right axis:{' '}
            <strong className="text-gray-700 ml-1">{rightUnit}</strong>
          </span>
        </div>
      )}

      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={data}
          syncId={syncId}
          margin={{ top: 8, right: rightMargin, left: 0, bottom: 8 }}
          onMouseMove={(state) => {
            if (!onHoverPoint) return;
            const indexRaw = state?.activeTooltipIndex;
            const index =
              typeof indexRaw === 'number'
                ? indexRaw
                : typeof indexRaw === 'string'
                  ? Number(indexRaw)
                  : Number.NaN;
            if (Number.isNaN(index) || index < 0 || index >= data.length) {
              onHoverPoint(null);
              return;
            }

            const point = data[index];
            if (!point || typeof point.time !== 'string') {
              onHoverPoint(null);
              return;
            }
            const values: Record<string, number> = {};
            for (const parameter of series) {
              const value = point[parameter.parameter_name];
              if (typeof value !== 'number' || Number.isNaN(value)) continue;
              values[parameter.parameter_name] = value;
            }
            onHoverPoint({ timestamp: point.time, values });
          }}
          onMouseLeave={() => {
            onHoverPoint?.(null);
          }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />

          <XAxis
            dataKey="time"
            tickFormatter={formatTimestamp}
            tick={{ fontSize: 11, fill: '#9ca3af' }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickLine={false}
            minTickGap={60}
          />

          {/* Left Y-axis */}
          <YAxis
            yAxisId="left"
            orientation="left"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={false}
            tickLine={false}
            width={58}
            domain={leftHasBinary ? [-0.2, 1.5] : ['auto', 'auto']}
            tickFormatter={(v: number) =>
              v.toLocaleString(undefined, { maximumFractionDigits: 2 })
            }
            label={
              leftUnit
                ? ({
                    value: leftUnit,
                    angle: -90,
                    position: 'insideLeft',
                    offset: 10,
                    style: { fontSize: 11, fill: '#9ca3af' },
                  } as object)
                : undefined
            }
          />

          {/* Right Y-axis — only rendered when there are series on it */}
          {hasDualAxis && (
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 11, fill: '#6b7280' }}
              axisLine={false}
              tickLine={false}
              width={58}
              domain={rightHasBinary ? [-0.2, 1.5] : ['auto', 'auto']}
              tickFormatter={(v: number) =>
                v.toLocaleString(undefined, { maximumFractionDigits: 2 })
              }
              label={
                rightUnit
                  ? ({
                      value: rightUnit,
                      angle: 90,
                      position: 'insideRight',
                      offset: 10,
                      style: { fontSize: 11, fill: '#9ca3af' },
                    } as object)
                  : undefined
              }
            />
          )}

          <Tooltip
            content={
              <CustomTooltip seriesMeta={seriesMeta} />
            }
            cursor={{ stroke: '#94a3b8', strokeDasharray: '4 4' }}
          />

          <Legend
            content={<CustomLegend seriesMeta={seriesMeta} />}
          />

          {/* Lines for left axis */}
          {leftSeries.map((s) => (
            <Line
              key={s.parameter_name}
              yAxisId="left"
              type={binaryNames.has(s.parameter_name) ? 'stepAfter' : 'monotone'}
              dataKey={s.parameter_name}
              stroke={COLORS[colorIndex.get(s.parameter_name)! % COLORS.length]}
              strokeWidth={binaryNames.has(s.parameter_name) ? 2.5 : 2}
              dot={false}
              activeDot={{ r: 4 }}
              connectNulls
            />
          ))}

          {/* Lines for right axis */}
          {rightSeries.map((s) => (
            <Line
              key={s.parameter_name}
              yAxisId="right"
              type={binaryNames.has(s.parameter_name) ? 'stepAfter' : 'monotone'}
              dataKey={s.parameter_name}
              stroke={COLORS[colorIndex.get(s.parameter_name)! % COLORS.length]}
              strokeWidth={binaryNames.has(s.parameter_name) ? 2.5 : 2}
              strokeDasharray={binaryNames.has(s.parameter_name) ? undefined : '5 3'}
              dot={false}
              activeDot={{ r: 4 }}
              connectNulls
            />
          ))}

          {/* Mean reference lines */}
          {showReferenceMean &&
            series.map((s) => {
              const axis =
                seriesMeta.get(s.parameter_name)?.axis ?? 'left';
              return (
                <ReferenceLine
                  key={`mean-${s.parameter_name}`}
                  yAxisId={axis}
                  y={s.statistics.mean}
                  stroke={
                    COLORS[colorIndex.get(s.parameter_name)! % COLORS.length]
                  }
                  strokeDasharray="6 3"
                  strokeOpacity={0.5}
                  label={{
                    value: `μ ${s.statistics.mean.toFixed(2)}`,
                    position: 'insideTopRight',
                    fontSize: 10,
                    fill: COLORS[
                      colorIndex.get(s.parameter_name)! % COLORS.length
                    ],
                  }}
                />
              );
            })}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
