import { CheckCircle, XCircle, Clock, Loader2, FileText } from 'lucide-react';
import { UploadRecord } from '../services/api';
import { cn } from '@/lib/utils';

interface UploadHistoryTableProps {
  records: UploadRecord[];
  isLoading: boolean;
}

function StatusBadge({ status }: { status: UploadRecord['status'] }) {
  const map = {
    success: {
      icon: <CheckCircle className="w-3.5 h-3.5" />,
      label: 'Success',
      cls: 'text-green-700 bg-green-50 border-green-200',
    },
    failed: {
      icon: <XCircle className="w-3.5 h-3.5" />,
      label: 'Failed',
      cls: 'text-red-700 bg-red-50 border-red-200',
    },
    pending: {
      icon: <Clock className="w-3.5 h-3.5" />,
      label: 'Pending',
      cls: 'text-yellow-700 bg-yellow-50 border-yellow-200',
    },
    processing: {
      icon: <Loader2 className="w-3.5 h-3.5 animate-spin" />,
      label: 'Processing',
      cls: 'text-blue-700 bg-blue-50 border-blue-200',
    },
  };

  const { icon, label, cls } = map[status];

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-medium',
        cls
      )}
    >
      {icon}
      {label}
    </span>
  );
}

function formatDateTime(dateString: string): string {
  return new Date(dateString).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function UploadHistoryTable({ records, isLoading }: UploadHistoryTableProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-10 gap-3 text-gray-400">
        <Loader2 className="w-5 h-5 animate-spin" />
        <span className="text-sm">Loading upload history…</span>
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 gap-3 text-center">
        <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center">
          <FileText className="w-6 h-6 text-gray-400" />
        </div>
        <p className="text-sm text-gray-500">No uploads yet.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
              File
            </th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Type
            </th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Rows
            </th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Status
            </th>
            <th className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Uploaded
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {records.map((record) => (
            <tr key={record.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3">
                <span className="font-medium text-gray-900 truncate max-w-[200px] block">
                  {record.filename}
                </span>
                {record.error_message && (
                  <span className="text-xs text-red-500 block mt-0.5 truncate max-w-[200px]">
                    {record.error_message}
                  </span>
                )}
              </td>
              <td className="px-4 py-3">
                <span className="uppercase text-xs font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                  {record.file_type}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-600">
                {record.row_count !== null ? record.row_count.toLocaleString() : '—'}
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={record.status} />
              </td>
              <td className="px-4 py-3 text-gray-500 text-xs">
                {formatDateTime(record.created_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
