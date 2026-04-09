import { useEffect, useState } from 'react';
import { Info } from 'lucide-react';
import Sidebar from '../components/Sidebar';
import DropZone from '../components/DropZone';
import UploadProgress, { UploadStatus } from '../components/UploadProgress';
import UploadHistoryTable from '../components/UploadHistoryTable';
import { ToastContainer, useToast } from '../components/ui/toast';
import { ApiService, FlightTest, UploadRecord } from '../services/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';

export default function Upload() {
  const toast = useToast();

  // Flight test selector
  const [flightTests, setFlightTests] = useState<FlightTest[]>([]);
  const [selectedTestId, setSelectedTestId] = useState<number | ''>('');
  const [loadingTests, setLoadingTests] = useState(true);

  // Upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState('');
  const [lastRowCount, setLastRowCount] = useState<number | undefined>(undefined);

  // History
  const [history, setHistory] = useState<UploadRecord[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Load flight tests for the selector
  useEffect(() => {
    ApiService.getFlightTests()
      .then(setFlightTests)
      .catch(() => toast.error('Could not load flight tests'))
      .finally(() => setLoadingTests(false));
  }, []);

  // Load upload history when a flight test is selected
  useEffect(() => {
    if (!selectedTestId) {
      setHistory([]);
      return;
    }
    let active = true;

    const refreshHistory = async (showLoading = false) => {
      if (showLoading) setLoadingHistory(true);
      try {
        const records = await ApiService.getUploadHistory(Number(selectedTestId));
        if (active) setHistory(records);
      } catch {
        if (active) setHistory([]);
      } finally {
        if (showLoading && active) setLoadingHistory(false);
      }
    };

    refreshHistory(true);
    const timer = window.setInterval(() => refreshHistory(false), 5000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [selectedTestId]);

  const handleUpload = async () => {
    if (!selectedFile || !selectedTestId) return;

    setUploadStatus('uploading');
    setUploadProgress(0);
    setUploadError('');
    setLastRowCount(undefined);

    try {
      const result = await ApiService.uploadFile(
        Number(selectedTestId),
        selectedFile,
        setUploadProgress
      );

      setUploadStatus('success');
      const rowCount = result.rows_processed ?? result.row_count ?? 0;
      setLastRowCount(rowCount);
      setSelectedFile(null);
      const deletedMsg = result.previous_data_points_deleted
        ? ` (replaced ${result.previous_data_points_deleted.toLocaleString()} previous data points)`
        : '';
      toast.success('Upload complete', `${rowCount.toLocaleString()} rows imported from "${result.filename ?? selectedFile.name}"${deletedMsg}.`);

      // Refresh history
      const updated = await ApiService.getUploadHistory(Number(selectedTestId)).catch(() => []);
      setHistory(updated);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Upload failed';
      setUploadStatus('error');
      setUploadError(msg);
      toast.error('Upload failed', msg);
    }
  };

  const handleReset = () => {
    setUploadStatus('idle');
    setUploadProgress(0);
    setUploadError('');
    setLastRowCount(undefined);
    setSelectedFile(null);
  };

  const canUpload =
    !!selectedFile && !!selectedTestId && uploadStatus !== 'uploading';

  return (
    <Sidebar>
      <div className="p-8 max-w-3xl">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-1">Upload Data</h1>
          <p className="text-gray-500">Import flight test data from CSV files</p>
        </div>

        {/* Upload Card */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Import File</CardTitle>
            <CardDescription>
              Select a flight test, then upload a CSV file containing the data.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {/* Flight test selector */}
            <div className="space-y-1.5">
              <label
                htmlFor="flight-test-select"
                className="block text-sm font-medium text-gray-700"
              >
                Flight Test <span className="text-red-500">*</span>
              </label>
              <select
                id="flight-test-select"
                value={selectedTestId}
                onChange={(e) => {
                  setSelectedTestId(e.target.value === '' ? '' : Number(e.target.value));
                  handleReset();
                }}
                disabled={loadingTests || uploadStatus === 'uploading'}
                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900
                           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                           disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <option value="">
                  {loadingTests ? 'Loading flight tests…' : '— Select a flight test —'}
                </option>
                {flightTests.map((t) => (
                  <option key={t.id} value={t.id}>
                    #{t.id} · {t.test_name} ({t.aircraft_type})
                  </option>
                ))}
              </select>
            </div>

            {/* Drop zone */}
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-700">
                Data File <span className="text-red-500">*</span>
              </label>
              <DropZone
                onFileSelected={setSelectedFile}
                disabled={!selectedTestId || uploadStatus === 'uploading'}
              />
            </div>

            {/* Upload progress */}
            <UploadProgress
              status={uploadStatus}
              progress={uploadProgress}
              filename={selectedFile?.name}
              errorMessage={uploadError}
              rowCount={lastRowCount}
            />

            {/* Action buttons */}
            <div className="flex gap-3">
              <Button
                onClick={handleUpload}
                disabled={!canUpload}
                className="flex-1"
              >
                {uploadStatus === 'uploading' ? 'Uploading…' : 'Upload File'}
              </Button>
              {(uploadStatus === 'success' || uploadStatus === 'error') && (
                <Button variant="outline" onClick={handleReset}>
                  Upload Another
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Format guide */}
        <Card className="mb-6 border-blue-100 bg-blue-50/50">
          <CardContent className="pt-5">
            <div className="flex gap-3">
              <Info className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
              <div className="space-y-2 text-sm text-blue-800">
                <p className="font-semibold">Expected file format</p>
                <p>
                  The first row must contain column headers. Each subsequent row represents one
                  data point. Accepted format: <strong>.csv</strong> (max 50 MB).
                </p>
                <p>
                  Required structure:{' '}
                  row 1 = parameter names, row 2 = units, rows 3+ = data with a timestamp column
                  named{' '}
                  <code className="bg-blue-100 px-1 py-0.5 rounded text-xs">timestamp</code>,{' '}
                  <code className="bg-blue-100 px-1 py-0.5 rounded text-xs">time</code>, or{' '}
                  <code className="bg-blue-100 px-1 py-0.5 rounded text-xs">description</code>.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Upload history */}
        {selectedTestId && (
          <Card>
            <CardHeader>
              <CardTitle>Upload History</CardTitle>
              <CardDescription>
                Previous uploads for the selected flight test
              </CardDescription>
            </CardHeader>
            <CardContent>
              <UploadHistoryTable records={history} isLoading={loadingHistory} />
            </CardContent>
          </Card>
        )}
      </div>

      <ToastContainer toasts={toast.toasts} onDismiss={toast.dismiss} />
    </Sidebar>
  );
}
