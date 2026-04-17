import { useEffect, useState, useMemo } from 'react';
import {
  BarChart3,
  TrendingUp,
  ScatterChart,
  Info,
  RefreshCw,
  AlertCircle,
  Download,
  Loader2,
} from 'lucide-react';
import { useChartDownload } from '../hooks/useChartDownload';
import Sidebar from '../components/Sidebar';
import TimeSeriesChart, {
  TimeSeriesEventMarker,
  TimeSeriesHoverSnapshot,
  TimeSeriesThresholdOverlay,
} from '../components/TimeSeriesChart';
import CorrelationChart from '../components/CorrelationChart';
import StatCard from '../components/StatCard';
import ParameterExplorerPanel from '../components/ParameterExplorerPanel';
import { ToastContainer, useToast } from '../components/ui/toast';
import {
  ApiService,
  DatasetVersion,
  FlightTest,
  ParameterInfo,
  ParameterSeries,
} from '../services/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { cn } from '@/lib/utils';

type ChartTab = 'timeseries' | 'correlation';

function formatTimeCursor(timestamp: string): string {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return timestamp;
  return parsed.toLocaleTimeString('en-US', { hour12: false });
}

function formatCursorValue(value: number | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function buildDemoEventMarkers(seriesData: ParameterSeries[]): TimeSeriesEventMarker[] {
  if (seriesData.length === 0 || seriesData[0].data.length === 0) return [];

  const base = [...seriesData[0].data].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );
  if (base.length === 0) return [];

  const markers: TimeSeriesEventMarker[] = [];
  const start = base[0];
  const mid = base[Math.floor((base.length - 1) / 2)];
  const end = base[base.length - 1];
  markers.push({ timestamp: start.timestamp, label: 'Start', color: '#1d4ed8' });
  if (mid.timestamp !== start.timestamp && mid.timestamp !== end.timestamp) {
    markers.push({ timestamp: mid.timestamp, label: 'Midpoint', color: '#7c3aed' });
  }
  if (end.timestamp !== start.timestamp) {
    markers.push({ timestamp: end.timestamp, label: 'End', color: '#dc2626' });
  }

  const wowSeries = seriesData.find((s) => {
    const key = s.parameter_name.toLowerCase();
    return key.includes('weightonwheels') || key.includes('wow');
  });
  if (wowSeries) {
    const wow = [...wowSeries.data].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
    for (let i = 1; i < wow.length; i += 1) {
      if (wow[i - 1].value >= 0.5 && wow[i].value < 0.5) {
        markers.push({
          timestamp: wow[i].timestamp,
          label: 'WOW Transition',
          color: '#0f766e',
        });
        break;
      }
    }
  }

  return markers
    .reduce<TimeSeriesEventMarker[]>((acc, marker) => {
      if (acc.some((existing) => existing.timestamp === marker.timestamp)) return acc;
      acc.push(marker);
      return acc;
    }, [])
    .slice(0, 8);
}

export default function Parameters() {
  const toast = useToast();

  // Flight test selector
  const [flightTests, setFlightTests] = useState<FlightTest[]>([]);
  const [selectedTestId, setSelectedTestId] = useState<number | ''>('');
  const [loadingTests, setLoadingTests] = useState(true);
  const [datasetVersions, setDatasetVersions] = useState<DatasetVersion[]>([]);
  const [loadingDatasetVersions, setLoadingDatasetVersions] = useState(false);
  const [selectedDatasetVersionId, setSelectedDatasetVersionId] = useState<number | ''>('');
  const [activatingDataset, setActivatingDataset] = useState(false);

  // Parameter list
  const [parameters, setParameters] = useState<ParameterInfo[]>([]);
  const [loadingParams, setLoadingParams] = useState(false);
  const [paramsError, setParamsError] = useState('');

  // Selected parameters (for chart)
  const [selectedParams, setSelectedParams] = useState<Set<string>>(new Set());

  // Chart data
  const [seriesData, setSeriesData] = useState<ParameterSeries[]>([]);
  const [compareSeriesData, setCompareSeriesData] = useState<ParameterSeries[]>([]);
  const [hoverSnapshot, setHoverSnapshot] = useState<TimeSeriesHoverSnapshot | null>(null);
  const [loadingChart, setLoadingChart] = useState(false);
  const [loadingCompareChart, setLoadingCompareChart] = useState(false);
  const [chartError, setChartError] = useState('');

  // UI state
  const [activeTab, setActiveTab] = useState<ChartTab>('timeseries');
  const [showMean, setShowMean] = useState(false);
  const [showEventMarkers, setShowEventMarkers] = useState(false);
  const [thresholdLowerInput, setThresholdLowerInput] = useState('');
  const [thresholdUpperInput, setThresholdUpperInput] = useState('');
  const [showThresholdBand, setShowThresholdBand] = useState(true);
  const [thresholdAxis, setThresholdAxis] = useState<'left' | 'right'>('left');
  const [compareModeEnabled, setCompareModeEnabled] = useState(false);
  const [compareDatasetVersionId, setCompareDatasetVersionId] = useState<number | ''>('');

  // Chart download
  const { chartRef, downloadChart, downloading } = useChartDownload();

  const selectedTestName = flightTests.find((t) => t.id === selectedTestId)?.test_name ?? 'chart';

  function handleDownloadChart() {
    const paramNames = Array.from(selectedParams).join('_').replace(/\s+/g, '-').slice(0, 40);
    const label = activeTab === 'timeseries' ? paramNames : `${corrX}_vs_${corrY}`;
    downloadChart(`FTIAS_${label}_${selectedTestName.replace(/\s+/g, '_')}`, {
      scale: 3,
      includeContainer: activeTab === 'timeseries',
      backgroundColor: '#ffffff',
    });
  }

  // Correlation axis selections
  const [corrX, setCorrX] = useState('');
  const [corrY, setCorrY] = useState('');
  const [corrSeriesData, setCorrSeriesData] = useState<ParameterSeries[]>([]);
  const [loadingCorr, setLoadingCorr] = useState(false);

  // Load flight tests
  useEffect(() => {
    ApiService.getFlightTests()
      .then(setFlightTests)
      .catch(() => toast.error('Could not load flight tests'))
      .finally(() => setLoadingTests(false));
  }, []);

  // Load dataset versions when flight test changes.
  useEffect(() => {
    if (!selectedTestId) {
      setDatasetVersions([]);
      setSelectedDatasetVersionId('');
      setCompareDatasetVersionId('');
      setCompareModeEnabled(false);
      setParameters([]);
      setSelectedParams(new Set());
      setSeriesData([]);
      setCompareSeriesData([]);
      return;
    }
    setLoadingDatasetVersions(true);
    setParamsError('');
    setParameters([]);
    setSelectedParams(new Set());
    setSeriesData([]);
    setCompareSeriesData([]);
    setCompareModeEnabled(false);
    setCompareDatasetVersionId('');
    setCorrX('');
    setCorrY('');
    setCorrSeriesData([]);

    ApiService.getDatasetVersions(Number(selectedTestId))
      .then((versions) => {
        setDatasetVersions(versions);
        const preferred =
          versions.find((v) => v.is_active)?.id ?? versions.find((v) => v.status === 'success')?.id;
        setSelectedDatasetVersionId(preferred ?? '');
      })
      .catch((err) => {
        setDatasetVersions([]);
        setSelectedDatasetVersionId('');
        toast.error(
          'Could not load dataset versions',
          err instanceof Error ? err.message : 'Failed to load dataset versions'
        );
      })
      .finally(() => setLoadingDatasetVersions(false));
  }, [selectedTestId]);

  // Load parameters when selected flight test or dataset version changes.
  useEffect(() => {
    if (!selectedTestId) {
      return;
    }
    setLoadingParams(true);
    setParamsError('');
    setParameters([]);
    setSelectedParams(new Set());
    setSeriesData([]);

    const datasetVersionId =
      selectedDatasetVersionId === '' ? undefined : Number(selectedDatasetVersionId);
    ApiService.getParametersForDataset(Number(selectedTestId), datasetVersionId)
      .then((params) => {
        setParameters(params);
        if (params.length > 0) {
          setSelectedParams(new Set([params[0].name]));
        }
      })
      .catch((err) => {
        setParamsError(err instanceof Error ? err.message : 'Failed to load parameters');
      })
      .finally(() => setLoadingParams(false));
  }, [selectedTestId, selectedDatasetVersionId]);

  // Fetch chart data whenever selected parameters change
  useEffect(() => {
    if (!selectedTestId || selectedParams.size === 0) {
      setSeriesData([]);
      return;
    }
    setLoadingChart(true);
    setChartError('');

    const datasetVersionId =
      selectedDatasetVersionId === '' ? undefined : Number(selectedDatasetVersionId);
    ApiService.getParameterData(
      Number(selectedTestId),
      Array.from(selectedParams),
      datasetVersionId
    )
      .then(setSeriesData)
      .catch((err) => {
        setChartError(err instanceof Error ? err.message : 'Failed to load chart data');
      })
      .finally(() => setLoadingChart(false));
  }, [selectedTestId, selectedParams, selectedDatasetVersionId]);

  useEffect(() => {
    if (
      !compareModeEnabled ||
      !selectedTestId ||
      compareDatasetVersionId === '' ||
      selectedParams.size === 0
    ) {
      setCompareSeriesData([]);
      return;
    }
    setLoadingCompareChart(true);

    ApiService.getParameterData(
      Number(selectedTestId),
      Array.from(selectedParams),
      Number(compareDatasetVersionId)
    )
      .then(setCompareSeriesData)
      .catch(() => setCompareSeriesData([]))
      .finally(() => setLoadingCompareChart(false));
  }, [
    compareModeEnabled,
    selectedTestId,
    selectedParams,
    compareDatasetVersionId,
  ]);

  useEffect(() => {
    setHoverSnapshot(null);
  }, [
    selectedTestId,
    selectedDatasetVersionId,
    compareDatasetVersionId,
    compareModeEnabled,
    selectedParams,
    activeTab,
  ]);

  const toggleParam = (name: string) => {
    setSelectedParams((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        if (next.size >= 8) {
          toast.warning('Limit reached', 'You can overlay up to 8 parameters at once.');
          return prev;
        }
        next.add(name);
      }
      return next;
    });
  };

  const applyParameterSet = (names: string[]) => {
    const available = new Set(parameters.map((p) => p.name));
    const validNames = names.filter((name) => available.has(name));
    const missingNames = names.filter((name) => !available.has(name));
    const limited = validNames.slice(0, 8);
    setSelectedParams(new Set(limited));

    if (validNames.length === 0) {
      toast.warning('Saved set is empty', 'No parameters from this set exist in the current dataset.');
      return;
    }
    if (missingNames.length > 0) {
      toast.warning(
        'Some parameters are unavailable',
        `${missingNames.length} parameter(s) from this set are missing in the selected dataset version.`
      );
    }
    if (validNames.length > 8) {
      toast.warning('Set truncated', 'Only the first 8 parameters were applied.');
    }
  };

  // Fetch correlation data independently when X or Y axis selection changes
  useEffect(() => {
    if (!selectedTestId || !corrX || !corrY) {
      setCorrSeriesData([]);
      return;
    }
    // Avoid duplicate fetch if both are the same
    const toFetch = corrX === corrY ? [corrX] : [corrX, corrY];
    setLoadingCorr(true);
    const datasetVersionId =
      selectedDatasetVersionId === '' ? undefined : Number(selectedDatasetVersionId);
    ApiService.getParameterData(Number(selectedTestId), toFetch, datasetVersionId)
      .then(setCorrSeriesData)
      .catch(() => setCorrSeriesData([]))
      .finally(() => setLoadingCorr(false));
  }, [selectedTestId, corrX, corrY, selectedDatasetVersionId]);

  // Correlation: x and y series from independently-fetched data
  const corrXSeries = useMemo(
    () => corrSeriesData.find((s) => s.parameter_name === corrX),
    [corrSeriesData, corrX]
  );
  const corrYSeries = useMemo(
    () => corrSeriesData.find((s) => s.parameter_name === corrY),
    [corrSeriesData, corrY]
  );

  // Stats for selected parameters
  const stats = useMemo(
    () => seriesData.filter((s) => selectedParams.has(s.parameter_name)),
    [seriesData, selectedParams]
  );
  const hasRightAxis = useMemo(() => {
    const units = new Set(seriesData.map((series) => series.unit ?? 'value'));
    return units.size > 1;
  }, [seriesData]);
  const eventMarkers = useMemo(
    () => (showEventMarkers ? buildDemoEventMarkers(seriesData) : []),
    [showEventMarkers, seriesData]
  );
  const thresholdOverlay = useMemo<TimeSeriesThresholdOverlay | undefined>(() => {
    const lower = thresholdLowerInput.trim() === '' ? undefined : Number(thresholdLowerInput);
    const upper = thresholdUpperInput.trim() === '' ? undefined : Number(thresholdUpperInput);
    const hasValidLower = typeof lower === 'number' && !Number.isNaN(lower);
    const hasValidUpper = typeof upper === 'number' && !Number.isNaN(upper);
    if (!hasValidLower && !hasValidUpper) return undefined;
    return {
      lowerLimit: hasValidLower ? lower : undefined,
      upperLimit: hasValidUpper ? upper : undefined,
      showBand: showThresholdBand,
      axis: thresholdAxis,
      label: 'Threshold',
    };
  }, [thresholdLowerInput, thresholdUpperInput, showThresholdBand, thresholdAxis]);

  const selectedDatasetVersion = useMemo(() => {
    if (selectedDatasetVersionId === '') return undefined;
    return datasetVersions.find((v) => v.id === Number(selectedDatasetVersionId));
  }, [datasetVersions, selectedDatasetVersionId]);

  const compareDatasetCandidates = useMemo(
    () =>
      datasetVersions.filter(
        (version) =>
          version.status === 'success' &&
          (selectedDatasetVersionId === '' || version.id !== Number(selectedDatasetVersionId))
      ),
    [datasetVersions, selectedDatasetVersionId]
  );

  const compareDatasetVersion = useMemo(() => {
    if (compareDatasetVersionId === '') return undefined;
    return datasetVersions.find((v) => v.id === Number(compareDatasetVersionId));
  }, [datasetVersions, compareDatasetVersionId]);

  const activeDatasetVersion = useMemo(
    () => datasetVersions.find((v) => v.is_active),
    [datasetVersions]
  );

  useEffect(() => {
    if (!compareModeEnabled) {
      setCompareSeriesData([]);
      return;
    }
    const selectedId =
      compareDatasetVersionId === '' ? null : Number(compareDatasetVersionId);
    const isStillValid =
      selectedId != null &&
      compareDatasetCandidates.some((version) => version.id === selectedId);
    if (isStillValid) return;

    const fallback = compareDatasetCandidates[0]?.id;
    setCompareDatasetVersionId(fallback ?? '');
    if (!fallback) {
      setCompareSeriesData([]);
    }
  }, [compareModeEnabled, compareDatasetCandidates, compareDatasetVersionId]);

  const compareDatasetLabel =
    compareDatasetVersion?.label ??
    (compareDatasetVersionId === '' ? 'none' : `v${compareDatasetVersionId}`);

  const compareSeriesForChart = useMemo(() => {
    if (!compareModeEnabled || compareDatasetVersionId === '') return [];
    return compareSeriesData.map((series) => ({
      ...series,
      parameter_name: `${series.parameter_name} [${compareDatasetLabel}]`,
    }));
  }, [compareModeEnabled, compareDatasetVersionId, compareSeriesData, compareDatasetLabel]);

  const compareSeriesKeys = useMemo(
    () => compareSeriesForChart.map((series) => series.parameter_name),
    [compareSeriesForChart]
  );

  const combinedTimeSeriesData = useMemo(
    () =>
      compareModeEnabled
        ? [...seriesData, ...compareSeriesForChart]
        : seriesData,
    [compareModeEnabled, seriesData, compareSeriesForChart]
  );

  const compareMissingParameters = useMemo(() => {
    if (!compareModeEnabled || compareDatasetVersionId === '') return [];
    const returned = new Set(compareSeriesData.map((series) => series.parameter_name));
    return Array.from(selectedParams).filter((name) => !returned.has(name));
  }, [compareModeEnabled, compareDatasetVersionId, compareSeriesData, selectedParams]);

  const chartBusy =
    loadingChart || (activeTab === 'timeseries' && compareModeEnabled && loadingCompareChart);
  const parameterExplorerNamespace =
    selectedTestId === ''
      ? 'parameter-explorer:parameters-page:no-test'
      : `parameter-explorer:flight-test-${selectedTestId}`;

  async function handleActivateSelectedDataset() {
    if (!selectedTestId || selectedDatasetVersionId === '') return;
    const versionId = Number(selectedDatasetVersionId);
    setActivatingDataset(true);
    try {
      await ApiService.activateDatasetVersion(Number(selectedTestId), versionId);
      const versions = await ApiService.getDatasetVersions(Number(selectedTestId));
      setDatasetVersions(versions);
      toast.success(`Active dataset set to ${selectedDatasetVersion?.label ?? `v${versionId}`}`);
    } catch (err) {
      toast.error(
        'Failed to activate dataset',
        err instanceof Error ? err.message : 'Failed to activate dataset version'
      );
    } finally {
      setActivatingDataset(false);
    }
  }

  return (
    <Sidebar>
      <div className="p-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-1">Parameters</h1>
          <p className="text-gray-500">Visualize and analyze flight test parameters</p>
        </div>

        {/* Flight test selector */}
        <Card className="mb-6">
          <CardContent className="pt-5">
            <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
              <div className="flex-1">
                <label
                  htmlFor="param-test-select"
                  className="block text-sm font-medium text-gray-700 mb-1.5"
                >
                  Flight Test
                </label>
                <select
                  id="param-test-select"
                  value={selectedTestId}
                  onChange={(e) =>
                    setSelectedTestId(e.target.value === '' ? '' : Number(e.target.value))
                  }
                  disabled={loadingTests}
                  className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900
                             focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                             disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <option value="">
                    {loadingTests ? 'Loading…' : '— Select a flight test —'}
                  </option>
                  {flightTests.map((t) => (
                    <option key={t.id} value={t.id}>
                      #{t.id} · {t.test_name} ({t.aircraft_type})
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </CardContent>
        </Card>

        {selectedTestId && (
          <Card className="mb-6">
            <CardContent className="pt-5">
              <div className="flex flex-col gap-4">
                <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Dataset Version
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
                                 disabled:opacity-50 disabled:cursor-not-allowed"
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
                  <button
                    type="button"
                    onClick={handleActivateSelectedDataset}
                    disabled={
                      activatingDataset ||
                      selectedDatasetVersionId === '' ||
                      selectedDatasetVersion?.status !== 'success' ||
                      !!selectedDatasetVersion?.is_active
                    }
                    className={cn(
                      'inline-flex items-center justify-center rounded-lg border px-3 py-2 text-sm font-medium transition-colors',
                      'border-blue-200 text-blue-700 hover:bg-blue-50',
                      'disabled:cursor-not-allowed disabled:opacity-50'
                    )}
                  >
                    {activatingDataset ? 'Setting Active…' : 'Set as Active'}
                  </button>
                </div>

                <p className="text-xs text-gray-500">
                  {activeDatasetVersion
                    ? `Active dataset: ${activeDatasetVersion.label} (${activeDatasetVersion.data_points_count ?? 0} points)`
                    : 'No active dataset is set yet for this flight test.'}
                </p>

                <div className="rounded-lg border border-indigo-100 bg-indigo-50/70 p-3 space-y-2">
                  <label className="flex items-center gap-2 text-xs text-indigo-800">
                    <input
                      type="checkbox"
                      checked={compareModeEnabled}
                      onChange={(e) => setCompareModeEnabled(e.target.checked)}
                      className="rounded border-indigo-300 text-indigo-600 focus:ring-indigo-500"
                    />
                    Enable compare dataset overlay (same parameters, second dataset version)
                  </label>
                  {compareModeEnabled && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-end">
                      <div>
                        <label className="block text-xs font-medium text-indigo-700 mb-1">
                          Compare Against Dataset
                        </label>
                        <select
                          value={compareDatasetVersionId}
                          onChange={(e) =>
                            setCompareDatasetVersionId(
                              e.target.value === '' ? '' : Number(e.target.value)
                            )
                          }
                          disabled={compareDatasetCandidates.length === 0}
                          className="w-full rounded-md border border-indigo-200 bg-white px-2.5 py-1.5 text-xs text-gray-900
                                     focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:cursor-not-allowed
                                     disabled:opacity-50"
                        >
                          <option value="">
                            {compareDatasetCandidates.length === 0
                              ? 'No alternate successful dataset versions'
                              : '— Select compare dataset —'}
                          </option>
                          {compareDatasetCandidates.map((version) => (
                            <option key={version.id} value={version.id}>
                              {`${version.label} · ${version.data_points_count ?? 0} points`}
                            </option>
                          ))}
                        </select>
                      </div>
                      <p className="text-xs text-indigo-700">
                        Primary: <strong>{selectedDatasetVersion?.label ?? 'none'}</strong>
                        {compareDatasetVersionId !== '' ? (
                          <>
                            {' '}vs Compare: <strong>{compareDatasetLabel}</strong>
                          </>
                        ) : null}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {selectedTestId && (
          <Card className="mb-6 border-amber-200 bg-amber-50/60">
            <CardContent className="pt-5">
              <div className="flex gap-3">
                <Info className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                <div className="space-y-1 text-sm text-amber-900">
                  <p className="font-semibold">Dataset scope</p>
                  <p>
                    This page visualizes the <strong>selected dataset version</strong>.
                  </p>
                  <p>
                    Current selection:{' '}
                    <strong>{selectedDatasetVersion?.label ?? 'None selected'}</strong>.
                    Activate a version to make it the default dataset for other analysis surfaces.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Main content — only shown when a test is selected */}
        {selectedTestId ? (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Parameter list (left column) */}
            <div className="lg:col-span-1">
              <Card className="h-full">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm">Parameters</CardTitle>
                  <CardDescription className="text-xs">
                    Select up to 8 to overlay
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-0">
                  {loadingParams && (
                    <div className="flex items-center gap-2 py-6 text-gray-400 text-sm">
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      Loading…
                    </div>
                  )}

                  {paramsError && !loadingParams && (
                    <div className="flex items-start gap-2 text-red-500 text-xs py-4">
                      <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                      {paramsError}
                    </div>
                  )}

                  {!loadingParams && !paramsError && parameters.length === 0 && (
                    <p className="text-gray-400 text-sm py-4">
                      No parameters found. Upload data first.
                    </p>
                  )}

                  {!loadingParams && parameters.length > 0 && (
                    <ParameterExplorerPanel
                      parameters={parameters}
                      selectedParams={selectedParams}
                      maxSelection={8}
                      storageNamespace={parameterExplorerNamespace}
                      onToggleParam={toggleParam}
                      onApplyParameterSet={applyParameterSet}
                    />
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Chart area (right columns) */}
            <div className="lg:col-span-3 space-y-6">
              {/* Chart tabs */}
              <Card>
                <CardHeader className="pb-0">
                  <div className="flex items-center justify-between flex-wrap gap-3">
                    {/* Tab switcher */}
                    <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
                      <button
                        onClick={() => setActiveTab('timeseries')}
                        className={cn(
                          'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                          activeTab === 'timeseries'
                            ? 'bg-white text-gray-900 shadow-sm'
                            : 'text-gray-500 hover:text-gray-700'
                        )}
                      >
                        <TrendingUp className="w-4 h-4" />
                        Time Series
                      </button>
                      <button
                        onClick={() => setActiveTab('correlation')}
                        className={cn(
                          'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                          activeTab === 'correlation'
                            ? 'bg-white text-gray-900 shadow-sm'
                            : 'text-gray-500 hover:text-gray-700'
                        )}
                      >
                        <ScatterChart className="w-4 h-4" />
                        Correlation
                      </button>
                    </div>

                    <div className="flex items-center gap-2 flex-wrap">
                      {/* Time series options */}
                      {activeTab === 'timeseries' && (
                        <button
                          onClick={() => setShowMean((v) => !v)}
                          className={cn(
                            'text-xs px-3 py-1.5 rounded-lg border transition-colors',
                            showMean
                              ? 'bg-blue-50 border-blue-200 text-blue-700'
                              : 'border-gray-200 text-gray-500 hover:border-gray-300'
                          )}
                        >
                          {showMean ? '✓ ' : ''}Show mean line
                        </button>
                      )}

                      {/* Download chart button — shown when chart has data */}
                      {!chartBusy && !chartError &&
                        ((activeTab === 'timeseries' && seriesData.length > 0) ||
                          (activeTab === 'correlation' && corrXSeries && corrYSeries)) && (
                        <button
                          onClick={handleDownloadChart}
                          disabled={downloading}
                          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-gray-200
                                     text-gray-600 hover:border-blue-300 hover:text-blue-600 transition-colors
                                     disabled:opacity-50 disabled:cursor-not-allowed"
                          title="Download chart as PNG"
                        >
                          {downloading ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Download className="w-3.5 h-3.5" />
                          )}
                          {downloading ? 'Saving…' : 'Download PNG'}
                        </button>
                      )}
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="pt-4">
                  {activeTab === 'timeseries' && seriesData.length > 0 && (
                    <div className="mb-4 rounded-lg border border-gray-200 bg-gray-50 p-3 space-y-3">
                      <p className="text-xs font-semibold uppercase tracking-wide text-gray-600">
                        Engineering Overlays
                      </p>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <label className="flex items-center gap-2 text-xs text-gray-700">
                          <input
                            type="checkbox"
                            checked={showEventMarkers}
                            onChange={(e) => setShowEventMarkers(e.target.checked)}
                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                          />
                          Show event markers (demo/manual baseline)
                        </label>

                        <label className="flex items-center gap-2 text-xs text-gray-700">
                          <input
                            type="checkbox"
                            checked={showThresholdBand}
                            onChange={(e) => setShowThresholdBand(e.target.checked)}
                            className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                          />
                          Shade band between lower/upper limits
                        </label>
                      </div>

                      {compareModeEnabled && compareDatasetVersionId !== '' && compareMissingParameters.length > 0 && (
                        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                          Compare dataset is missing {compareMissingParameters.length} selected parameter(s):{' '}
                          <strong>{compareMissingParameters.slice(0, 4).join(', ')}</strong>
                          {compareMissingParameters.length > 4 ? ' ...' : ''}
                        </div>
                      )}

                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">
                            Lower Limit
                          </label>
                          <input
                            type="number"
                            value={thresholdLowerInput}
                            onChange={(e) => setThresholdLowerInput(e.target.value)}
                            placeholder="e.g. 0"
                            className="w-full rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-800
                                       focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">
                            Upper Limit
                          </label>
                          <input
                            type="number"
                            value={thresholdUpperInput}
                            onChange={(e) => setThresholdUpperInput(e.target.value)}
                            placeholder="e.g. 100"
                            className="w-full rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-800
                                       focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">
                            Threshold Axis
                          </label>
                          <select
                            value={thresholdAxis}
                            onChange={(e) => setThresholdAxis(e.target.value as 'left' | 'right')}
                            disabled={!hasRightAxis}
                            className="w-full rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-800
                                       focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50
                                       disabled:cursor-not-allowed"
                          >
                            <option value="left">Left axis</option>
                            <option value="right">Right axis</option>
                          </select>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* No parameters selected */}
                  {selectedParams.size === 0 && (
                    <div className="flex flex-col items-center justify-center h-64 gap-3 text-center">
                      <div className="w-14 h-14 bg-gray-100 rounded-full flex items-center justify-center">
                        <BarChart3 className="w-7 h-7 text-gray-400" />
                      </div>
                      <p className="text-gray-500 text-sm">
                        Select one or more parameters from the list to display a chart.
                      </p>
                    </div>
                  )}

                  {/* Loading chart */}
                  {chartBusy && selectedParams.size > 0 && (
                    <div className="flex flex-col items-center justify-center h-64 gap-3 text-gray-400">
                      <RefreshCw className="w-5 h-5 animate-spin" />
                      <span className="text-sm">
                        {compareModeEnabled && loadingCompareChart
                          ? 'Loading chart comparison data…'
                          : 'Loading chart data…'}
                      </span>
                      <span className="text-xs text-gray-300">Large datasets may take a few seconds</span>
                    </div>
                  )}

                  {/* Chart error */}
                  {chartError && !chartBusy && (
                    <div className="flex items-center justify-center h-64 gap-3 text-red-500 text-sm">
                      <AlertCircle className="w-5 h-5 shrink-0" />
                      {chartError}
                    </div>
                  )}

                  {/* Time series chart */}
                  {!chartBusy && !chartError && combinedTimeSeriesData.length > 0 && activeTab === 'timeseries' && (
                    <div ref={chartRef} className="bg-white space-y-2">
                      <div className="rounded-md border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-blue-900">
                        {hoverSnapshot ? (
                          <span>
                            Cursor at <strong>{formatTimeCursor(hoverSnapshot.timestamp)}</strong>
                            {': '}
                            {seriesData.map((item, idx) => (
                              <span key={`${item.parameter_name}-cursor`} className="inline-flex items-center">
                                {idx > 0 ? <span className="mx-1 text-blue-300">|</span> : null}
                                <strong>{item.parameter_name}</strong>
                                <span className="ml-1">{formatCursorValue(hoverSnapshot.values[item.parameter_name])}</span>
                                {item.unit ? <span className="ml-0.5 text-blue-700/70">{item.unit}</span> : null}
                              </span>
                            ))}
                          </span>
                        ) : (
                          <span>Move over the chart to inspect synchronized cursor values.</span>
                        )}
                      </div>
                      <TimeSeriesChart
                        series={combinedTimeSeriesData}
                        height={340}
                        showReferenceMean={showMean}
                        syncId={`parameters-timeseries-${selectedTestId}`}
                        onHoverPoint={setHoverSnapshot}
                        thresholdOverlay={thresholdOverlay}
                        eventMarkers={eventMarkers}
                        compareSeriesKeys={compareSeriesKeys}
                      />
                    </div>
                  )}

                  {/* Correlation chart */}
                  {!loadingChart && !chartError && activeTab === 'correlation' && (
                    <div className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">
                            X Axis
                          </label>
                          <select
                            value={corrX}
                            onChange={(e) => { setCorrX(e.target.value); setCorrY(''); }}
                            className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm
                                       focus:outline-none focus:ring-2 focus:ring-blue-500"
                          >
                            <option value="">— Select parameter —</option>
                            {parameters.map((p) => (
                              <option key={p.name} value={p.name}>
                                {p.name}{p.unit ? ` (${p.unit})` : ''}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">
                            Y Axis
                          </label>
                          <select
                            value={corrY}
                            onChange={(e) => setCorrY(e.target.value)}
                            disabled={!corrX}
                            className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm
                                       focus:outline-none focus:ring-2 focus:ring-blue-500
                                       disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <option value="">— Select parameter —</option>
                            {parameters
                              .filter((p) => p.name !== corrX)
                              .map((p) => (
                                <option key={p.name} value={p.name}>
                                  {p.name}{p.unit ? ` (${p.unit})` : ''}
                                </option>
                              ))}
                          </select>
                        </div>
                      </div>

                      {loadingCorr && (
                        <div className="flex items-center justify-center h-48 gap-3 text-gray-400">
                          <RefreshCw className="w-5 h-5 animate-spin" />
                          <span className="text-sm">Loading correlation data…</span>
                        </div>
                      )}

                      {!loadingCorr && corrXSeries && corrYSeries ? (
                        <div ref={chartRef} className="bg-white">
                          <CorrelationChart
                            xSeries={corrXSeries}
                            ySeries={corrYSeries}
                            height={300}
                          />
                        </div>
                      ) : !loadingCorr && (
                        <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
                          Select parameters for both axes to display the scatter plot.
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Statistics panel */}
              {stats.length > 0 && !chartBusy && (
                <div className="space-y-4">
                  {stats.map((s) => (
                    <Card key={s.parameter_name}>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-sm">
                          {s.parameter_name}
                          {s.unit && (
                            <span className="ml-2 text-xs font-normal text-gray-400">
                              ({s.unit})
                            </span>
                          )}
                        </CardTitle>
                        <CardDescription className="text-xs space-y-1">
                          <div>{s.statistics.count.toLocaleString()} data points</div>
                          {hoverSnapshot ? (
                            <div className="text-blue-700">
                              Cursor @ {formatTimeCursor(hoverSnapshot.timestamp)}:{' '}
                              {formatCursorValue(hoverSnapshot.values[s.parameter_name])}
                              {s.unit ? ` ${s.unit}` : ''}
                            </div>
                          ) : null}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="pt-0">
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                          <StatCard
                            label="Min"
                            value={s.statistics.min}
                            unit={s.unit}
                            accent="blue"
                          />
                          <StatCard
                            label="Max"
                            value={s.statistics.max}
                            unit={s.unit}
                            accent="orange"
                          />
                          <StatCard
                            label="Mean"
                            value={s.statistics.mean}
                            unit={s.unit}
                            accent="green"
                          />
                          <StatCard
                            label="Std Dev"
                            value={s.statistics.std_dev}
                            unit={s.unit}
                            accent="purple"
                          />
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Empty state — no test selected */
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center">
              <BarChart3 className="w-10 h-10 text-gray-400" />
            </div>
            <div className="text-center">
              <h3 className="text-lg font-semibold text-gray-900 mb-1">
                Select a flight test to begin
              </h3>
              <p className="text-gray-500 text-sm">
                Choose a flight test above to explore its parameters and visualize data.
              </p>
            </div>
          </div>
        )}
      </div>

      <ToastContainer toasts={toast.toasts} onDismiss={toast.dismiss} />
    </Sidebar>
  );
}
