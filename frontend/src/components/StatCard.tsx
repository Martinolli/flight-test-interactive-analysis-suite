import { cn } from '@/lib/utils';

interface StatCardProps {
  label: string;
  value: string | number;
  unit?: string | null;
  accent?: 'blue' | 'green' | 'orange' | 'purple' | 'red';
}

const accents = {
  blue:   'bg-blue-50   border-blue-100  text-blue-600',
  green:  'bg-green-50  border-green-100 text-green-600',
  orange: 'bg-orange-50 border-orange-100 text-orange-600',
  purple: 'bg-purple-50 border-purple-100 text-purple-600',
  red:    'bg-red-50    border-red-100   text-red-600',
};

export default function StatCard({ label, value, unit, accent = 'blue' }: StatCardProps) {
  return (
    <div className={cn('rounded-xl border px-4 py-3', accents[accent])}>
      <p className="text-xs font-medium uppercase tracking-wide opacity-70 mb-1">{label}</p>
      <p className="text-xl font-bold">
        {typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 4 }) : value}
        {unit && <span className="text-sm font-normal ml-1 opacity-60">{unit}</span>}
      </p>
    </div>
  );
}
