import { useEffect, useState } from 'react';
import { Info } from 'lucide-react';
import Sidebar from '../components/Sidebar';
import DropZone from '../components/DropZone';
import UploadProgress, { UploadStatus } from '../components/UploadProgress';
import UploadHistoryTable from '../components/UploadHistoryTable';
import { ToastContainer, useToast } from '../components/ui/toast';
import { ApiService, DatasetVersion, FlightTest, UploadRecord } from '../services/api';
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
  const [datasetVersions, setDatasetVersions] = useState<DatasetVersion[]>([]);
  const [loadingDatasetVersions, setLoadingDatasetVersions] = useState(false);
  const [selectedDatasetVersionId, setSelectedDatasetVersionId] = useState<number | ''>('');
  const [activatingDataset, setActivatingDataset] = useState(false);

  const hasActiveIngestion = history.some(
    (record) => record.status === 'pending' || record.status === 'processing'
  );

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
      setDatasetVersions([]);
      setSelectedDatasetVersionId('');
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

    const refreshDatasetVersions = async () => {
      setLoadingDatasetVersions(true);
      try {
        const versions = await ApiService.getDatasetVersions(Number(selectedTestId));
        if (!active) return;
        setDatasetVersions(versions);
        const preferred =
          versions.find((v) => v.is_active)?.id ?? versions.find((v) => v.status === 'success')?.id;
        setSelectedDatasetVersionId(preferred ?? '');
      } catch {
        if (!active) return;
        setDatasetVersions([]);
        setSelectedDatasetVersionId('');
      } finally {
        if (active) setLoadingDatasetVersions(false);
      }
    };

    refreshHistory(true);
    refreshDatasetVersions();

    return () => {
      active = false;
    };
  }, [selectedTestId]);

  // Poll only while there are active ingestion sessions.
  useEffect(() => {
    if (!selectedTestId || !hasActiveIngestion) {
      return;
    }
    let active = true;
    const timer = window.setInterval(async () => {
      try {
        const records = await ApiService.getUploadHistory(Number(selectedTestId));
        if (active) setHistory(records);
      } catch {
        // Keep last-known UI state on transient polling failures.
      }
    }, 5000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [selectedTestId, hasActiveIngestion]);

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
      const versions = await ApiService.getDatasetVersions(Number(selectedTestId)).catch(() => []);
      setDatasetVersions(versions);
      if (result.dataset_version_id) {
        setSelectedDatasetVersionId(result.dataset_version_id);
      } else {
        const activeVersionId = versions.find((v) => v.is_active)?.id;
        setSelectedDatasetVersionId(activeVersionId ?? '');
      }
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

  const selectedDatasetVersion =
    selectedDatasetVersionId === ''
      ? undefined
      : datasetVersions.find((v) => v.id === Number(selectedDatasetVersionId));
  const activeDatasetVersion = datasetVersions.find((v) => v.is_active);

  const handleActivateDatasetVersion = async () => {
    if (!selectedTestId || selectedDatasetVersionId === '') return;
    setActivatingDataset(true);
    const versionId = Number(selectedDatasetVersionId);
    try {
      await ApiService.activateDatasetVersion(Number(selectedTestId), versionId);
      const versions = await ApiService.getDatasetVersions(Number(selectedTestId));
      setDatasetVersions(versions);
      toast.success(`Active dataset set to ${selectedDatasetVersion?.label ?? `v${versionId}`}`);
    } catch (err) {
      toast.error(
        'Failed to activate dataset',
        err instanceof Error ? err.message : 'Could not activate dataset version'
      );
    } finally {
      setActivatingDataset(false);
    }
  };

  return (
    <Sidebar>
      <div className="mx-auto flex h-[100dvh] w-full max-w-[1400px] flex-col p-3 sm:p-4 md:p-6 lg:p-8">
        {/* Header */}
        <div className="mb-6 shrink-0">
          <h1 className="text-3xl font-bold text-gray-900 mb-1">Upload Data</h1>
          <p className="text-gray-500">Import flight test data from CSV files</p>
        </div>

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto pr-1">
          {/* Upload Card */}
          <Card>
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
                             disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
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
              <div className="flex flex-wrap gap-3">
                <Button
                  onClick={handleUpload}
                  disabled={!canUpload}
                  className="flex-1 min-w-[180px]"
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
          <Card className="border-blue-100 bg-blue-50/50">
            <CardContent className="pt-5">
              <div className="flex gap-3">
                <Info className="mt-0.5 h-5 w-5 shrink-0 text-blue-500" />
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

          {/* Active dataset behavior notice */}
          <Card className="border-amber-200 bg-amber-50/60">
            <CardContent className="pt-5">
              <div className="flex gap-3">
                <Info className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
                <div className="space-y-1.5 text-sm text-amber-900">
                  <p className="font-semibold">Active dataset behavior</p>
                  <p>
                    <strong>Upload History</strong> is an ingestion audit trail. The{' '}
                    <strong>latest successful upload</strong> becomes the active dataset for this
                    flight test.
                  </p>
                  <p>
                    Dashboard, Parameters, and AI Analysis use the active dataset only.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {selectedTestId && (
            <Card>
              <CardHeader>
                <CardTitle>Dataset Versions</CardTitle>
                <CardDescription>
                  Select a historical version and optionally mark it as active.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Selected Version
                    </label>
                    <select
                      value={selectedDatasetVersionId}
                      onChange={(e) =>
                        setSelectedDatasetVersionId(
                          e.target.value === '' ? '' : Number(e.target.value)
                        )
                      }
                      disabled={loadingDatasetVersions || datasetVersions.length === 0}
                      className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900
                                 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                                 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <option value="">
                        {loadingDatasetVersions
                          ? 'Loading dataset versions…'
                          : datasetVersions.length === 0
                            ? 'No dataset versions available'
                            : '— Select dataset version —'}
                      </option>
                      {datasetVersions.map((version) => (
                        <option key={version.id} value={version.id}>
                          {`${version.label} · ${version.status} · ${version.data_points_count ?? 0} points`}
                        </option>
                      ))}
                    </select>
                  </div>
                  <Button
                    variant="outline"
                    onClick={handleActivateDatasetVersion}
                    disabled={
                      activatingDataset ||
                      selectedDatasetVersionId === '' ||
                      selectedDatasetVersion?.status !== 'success' ||
                      !!selectedDatasetVersion?.is_active
                    }
                    className="text-blue-600 border-blue-200 hover:bg-blue-50"
                  >
                    {activatingDataset ? 'Setting Active…' : 'Set as Active'}
                  </Button>
                </div>
                <p className="text-xs text-gray-500">
                  {activeDatasetVersion
                    ? `Active dataset: ${activeDatasetVersion.label}`
                    : 'No active dataset is set yet.'}
                </p>
              </CardContent>
            </Card>
          )}

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
                <div className="max-h-[380px] overflow-y-auto">
                  <UploadHistoryTable records={history} isLoading={loadingHistory} />
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <ToastContainer toasts={toast.toasts} onDismiss={toast.dismiss} />
    </Sidebar>
  );
}
