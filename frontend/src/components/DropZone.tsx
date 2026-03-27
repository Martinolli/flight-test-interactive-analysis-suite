import { useRef, useState, useCallback } from 'react';
import { Upload, FileText, X } from 'lucide-react';
import { cn } from '@/lib/utils';

const ACCEPTED_TYPES: Record<string, string[]> = {
  'text/csv': ['.csv'],
  'application/vnd.ms-excel': ['.xls'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
};

const ACCEPTED_EXTENSIONS = ['.csv', '.xls', '.xlsx'];
const MAX_SIZE_MB = 50;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase();
  if (ext === 'csv') return '📄';
  if (ext === 'xls' || ext === 'xlsx') return '📊';
  return '📁';
}

interface DropZoneProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export default function DropZone({ onFileSelected, disabled = false }: DropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState('');

  const validateAndSelect = useCallback(
    (file: File) => {
      setValidationError('');

      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      if (!ACCEPTED_EXTENSIONS.includes(ext)) {
        setValidationError(
          `Unsupported file type "${ext}". Please upload a CSV, XLS, or XLSX file.`
        );
        return;
      }

      if (file.size > MAX_SIZE_BYTES) {
        setValidationError(
          `File is too large (${formatBytes(file.size)}). Maximum size is ${MAX_SIZE_MB} MB.`
        );
        return;
      }

      setSelectedFile(file);
      onFileSelected(file);
    },
    [onFileSelected]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      if (disabled) return;
      const file = e.dataTransfer.files[0];
      if (file) validateAndSelect(file);
    },
    [disabled, validateAndSelect]
  );

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!disabled) setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) validateAndSelect(file);
    // Reset input so the same file can be re-selected after clearing
    e.target.value = '';
  };

  const handleClear = () => {
    setSelectedFile(null);
    setValidationError('');
  };

  return (
    <div className="space-y-3">
      {/* Drop area */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !disabled && !selectedFile && inputRef.current?.click()}
        className={cn(
          'relative border-2 border-dashed rounded-xl transition-all duration-200',
          isDragging
            ? 'border-blue-400 bg-blue-50 scale-[1.01]'
            : 'border-gray-200 bg-gray-50 hover:border-blue-300 hover:bg-blue-50/50',
          disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
          selectedFile ? 'border-green-300 bg-green-50' : ''
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={Object.keys(ACCEPTED_TYPES).join(',')}
          className="sr-only"
          onChange={handleInputChange}
          disabled={disabled}
        />

        {selectedFile ? (
          /* Selected file preview */
          <div className="flex items-center gap-4 p-5">
            <span className="text-3xl">{getFileIcon(selectedFile.name)}</span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-gray-900 truncate">{selectedFile.name}</p>
              <p className="text-xs text-gray-500 mt-0.5">{formatBytes(selectedFile.size)}</p>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleClear();
              }}
              disabled={disabled}
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-white transition-colors"
              aria-label="Remove file"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ) : (
          /* Empty drop area */
          <div className="flex flex-col items-center justify-center py-12 px-6 text-center">
            <div
              className={cn(
                'w-14 h-14 rounded-full flex items-center justify-center mb-4 transition-colors',
                isDragging ? 'bg-blue-100' : 'bg-white border border-gray-200'
              )}
            >
              <Upload
                className={cn('w-6 h-6', isDragging ? 'text-blue-500' : 'text-gray-400')}
              />
            </div>
            <p className="text-sm font-medium text-gray-700 mb-1">
              {isDragging ? 'Drop your file here' : 'Drag & drop your file here'}
            </p>
            <p className="text-xs text-gray-400 mb-3">or click to browse</p>
            <div className="flex items-center gap-2 flex-wrap justify-center">
              {ACCEPTED_EXTENSIONS.map((ext) => (
                <span
                  key={ext}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white border border-gray-200 text-xs text-gray-500"
                >
                  <FileText className="w-3 h-3" />
                  {ext.toUpperCase()}
                </span>
              ))}
              <span className="text-xs text-gray-400">· Max {MAX_SIZE_MB} MB</span>
            </div>
          </div>
        )}
      </div>

      {/* Validation error */}
      {validationError && (
        <p className="text-sm text-red-500 flex items-start gap-1.5">
          <span className="shrink-0 mt-0.5">⚠</span>
          {validationError}
        </p>
      )}
    </div>
  );
}
