import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

interface UploadProgressProps {
  status: UploadStatus;
  progress: number;       // 0–100
  filename?: string;
  errorMessage?: string;
  rowCount?: number;
}

export default function UploadProgress({
  status,
  progress,
  filename,
  errorMessage,
  rowCount,
}: UploadProgressProps) {
  if (status === 'idle') return null;

  return (
    <div
      className={cn(
        'rounded-xl border p-4 space-y-3 transition-all',
        status === 'uploading' && 'border-blue-200 bg-blue-50',
        status === 'success' && 'border-green-200 bg-green-50',
        status === 'error' && 'border-red-200 bg-red-50'
      )}
    >
      {/* Status header */}
      <div className="flex items-center gap-3">
        {status === 'uploading' && (
          <Loader2 className="w-5 h-5 text-blue-500 animate-spin shrink-0" />
        )}
        {status === 'success' && (
          <CheckCircle className="w-5 h-5 text-green-500 shrink-0" />
        )}
        {status === 'error' && (
          <XCircle className="w-5 h-5 text-red-500 shrink-0" />
        )}

        <div className="flex-1 min-w-0">
          <p
            className={cn(
              'text-sm font-medium',
              status === 'uploading' && 'text-blue-700',
              status === 'success' && 'text-green-700',
              status === 'error' && 'text-red-700'
            )}
          >
            {status === 'uploading' && `Uploading${filename ? ` "${filename}"` : ''}…`}
            {status === 'success' && 'Upload complete!'}
            {status === 'error' && 'Upload failed'}
          </p>

          {status === 'success' && rowCount !== undefined && (
            <p className="text-xs text-green-600 mt-0.5">
              {rowCount.toLocaleString()} row{rowCount !== 1 ? 's' : ''} imported successfully.
            </p>
          )}

          {status === 'error' && errorMessage && (
            <p className="text-xs text-red-600 mt-0.5">{errorMessage}</p>
          )}
        </div>

        {status === 'uploading' && (
          <span className="text-sm font-semibold text-blue-600 shrink-0">{progress}%</span>
        )}
      </div>

      {/* Progress bar (only while uploading) */}
      {status === 'uploading' && (
        <div className="h-2 bg-blue-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-300 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}
