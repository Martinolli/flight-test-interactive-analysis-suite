import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { ParameterSeries } from '../services/api';

interface CorrelationChartProps {
  xSeries: ParameterSeries;
  ySeries: ParameterSeries;
  height?: number;
}

interface ScatterPoint {
  x: number;
  y: number;
}

/**
 * Aligns two series by timestamp to produce (x, y) scatter pairs.
 */
function buildScatterData(
  xSeries: ParameterSeries,
  ySeries: ParameterSeries
): ScatterPoint[] {
  const yMap = new Map<string, number>();
  ySeries.data.forEach((pt) => yMap.set(pt.timestamp, pt.value));

  return xSeries.data
    .filter((pt) => yMap.has(pt.timestamp))
    .map((pt) => ({ x: pt.value, y: yMap.get(pt.timestamp)! }));
}

function CustomTooltip({
  active,
  payload,
  xLabel,
  yLabel,
}: {
  active?: boolean;
  payload?: { value: number }[];
  xLabel: string;
  yLabel: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-sm">
      <div className="flex justify-between gap-4">
        <span className="text-gray-500 truncate max-w-[80px]">{xLabel}</span>
        <span className="font-semibold text-gray-900">
          {payload[0]?.value?.toLocaleString(undefined, { maximumFractionDigits: 4 })}
        </span>
      </div>
      <div className="flex justify-between gap-4">
        <span className="text-gray-500 truncate max-w-[80px]">{yLabel}</span>
        <span className="font-semibold text-gray-900">
          {payload[1]?.value?.toLocaleString(undefined, { maximumFractionDigits: 4 })}
        </span>
      </div>
    </div>
  );
}

export default function CorrelationChart({
  xSeries,
  ySeries,
  height = 320,
}: CorrelationChartProps) {
  const data = buildScatterData(xSeries, ySeries);

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
        No overlapping timestamps between the selected parameters.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          type="number"
          dataKey="x"
          name={xSeries.parameter_name}
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          axisLine={{ stroke: '#e5e7eb' }}
          tickLine={false}
          label={{
            value: `${xSeries.parameter_name}${xSeries.unit ? ` (${xSeries.unit})` : ''}`,
            position: 'insideBottom',
            offset: -4,
            fontSize: 11,
            fill: '#6b7280',
          }}
        />
        <YAxis
          type="number"
          dataKey="y"
          name={ySeries.parameter_name}
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          axisLine={false}
          tickLine={false}
          width={52}
          label={{
            value: `${ySeries.parameter_name}${ySeries.unit ? ` (${ySeries.unit})` : ''}`,
            angle: -90,
            position: 'insideLeft',
            offset: 12,
            fontSize: 11,
            fill: '#6b7280',
          }}
        />
        <Tooltip
          content={
            <CustomTooltip
              xLabel={xSeries.parameter_name}
              yLabel={ySeries.parameter_name}
            />
          }
          cursor={{ strokeDasharray: '3 3' }}
        />
        <Scatter data={data} fill="#2563eb" fillOpacity={0.6} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}
