import { useEffect, useState, useMemo } from 'react';
import {
  BarChart3,
  TrendingUp,
  ScatterChart,
  RefreshCw,
  AlertCircle,
  CheckSquare,
  Square,
  Download,
  Loader2,
} from 'lucide-react';
import { useChartDownload } from '../hooks/useChartDownload';
import Sidebar from '../components/Sidebar';
import TimeSeriesChart from '../components/TimeSeriesChart';
import CorrelationChart from '../components/CorrelationChart';
import StatCard from '../components/StatCard';
import { ToastContainer, useToast } from '../components/ui/toast';
import { ApiService, FlightTest, ParameterInfo, ParameterSeries } from '../services/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { cn } from '@/lib/utils';

type ChartTab = 'timeseries' | 'correlation';

export default function Parameters() {
  const toast = useToast();

  // Flight test selector
  const [flightTests, setFlightTests] = useState<FlightTest[]>([]);
  const [selectedTestId, setSelectedTestId] = useState<number | ''>('');
  const [loadingTests, setLoadingTests] = useState(true);

  // Parameter list
  const [parameters, setParameters] = useState<ParameterInfo[]>([]);
  const [loadingParams, setLoadingParams] = useState(false);
  const [paramsError, setParamsError] = useState('');

  // Selected parameters (for chart)
  const [selectedParams, setSelectedParams] = useState<Set<string>>(new Set());

  // Chart data
  const [seriesData, setSeriesData] = useState<ParameterSeries[]>([]);
  const [loadingChart, setLoadingChart] = useState(false);
  const [chartError, setChartError] = useState('');

  // UI state
  const [activeTab, setActiveTab] = useState<ChartTab>('timeseries');
  const [showMean, setShowMean] = useState(false);

  // Chart download
  const { chartRef, downloadChart, downloading } = useChartDownload();

  const selectedTestName = flightTests.find((t) => t.id === selectedTestId)?.test_name ?? 'chart';

  function handleDownloadChart() {
    const paramNames = Array.from(selectedParams).join('_').replace(/\s+/g, '-').slice(0, 40);
    const label = activeTab === 'timeseries' ? paramNames : `${corrX}_vs_${corrY}`;
    downloadChart(`FTIAS_${label}_${selectedTestName.replace(/\s+/g, '_')}`);
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

  // Load parameters when flight test changes
  useEffect(() => {
    if (!selectedTestId) {
      setParameters([]);
      setSelectedParams(new Set());
      setSeriesData([]);
      return;
    }
    setLoadingParams(true);
    setParamsError('');
    setParameters([]);
    setSelectedParams(new Set());
    setSeriesData([]);

    ApiService.getParameters(Number(selectedTestId))
      .then((params) => {
        setParameters(params);
        // Auto-select first parameter if available
        if (params.length > 0) {
          setSelectedParams(new Set([params[0].name]));
        }
      })
      .catch((err) => {
        setParamsError(err instanceof Error ? err.message : 'Failed to load parameters');
      })
      .finally(() => setLoadingParams(false));
  }, [selectedTestId]);

  // Fetch chart data whenever selected parameters change
  useEffect(() => {
    if (!selectedTestId || selectedParams.size === 0) {
      setSeriesData([]);
      return;
    }
    setLoadingChart(true);
    setChartError('');

    ApiService.getParameterData(Number(selectedTestId), Array.from(selectedParams))
      .then(setSeriesData)
      .catch((err) => {
        setChartError(err instanceof Error ? err.message : 'Failed to load chart data');
      })
      .finally(() => setLoadingChart(false));
  }, [selectedTestId, selectedParams]);

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

  // Fetch correlation data independently when X or Y axis selection changes
  useEffect(() => {
    if (!selectedTestId || !corrX || !corrY) {
      setCorrSeriesData([]);
      return;
    }
    // Avoid duplicate fetch if both are the same
    const toFetch = corrX === corrY ? [corrX] : [corrX, corrY];
    setLoadingCorr(true);
    ApiService.getParameterData(Number(selectedTestId), toFetch)
      .then(setCorrSeriesData)
      .catch(() => setCorrSeriesData([]))
      .finally(() => setLoadingCorr(false));
  }, [selectedTestId, corrX, corrY]);

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
                    <ul className="space-y-1">
                      {parameters.map((p) => {
                        const isSelected = selectedParams.has(p.name);
                        return (
                          <li key={p.name}>
                            <button
                              onClick={() => toggleParam(p.name)}
                              className={cn(
                                'w-full flex items-start gap-2 px-2 py-2 rounded-lg text-left text-sm transition-colors',
                                isSelected
                                  ? 'bg-blue-50 text-blue-800'
                                  : 'text-gray-700 hover:bg-gray-50'
                              )}
                            >
                              {isSelected ? (
                                <CheckSquare className="w-4 h-4 shrink-0 mt-0.5 text-blue-600" />
                              ) : (
                                <Square className="w-4 h-4 shrink-0 mt-0.5 text-gray-400" />
                              )}
                              <div className="min-w-0">
                                <p className="font-medium truncate">{p.name}</p>
                                <p className="text-xs opacity-60 truncate">
                                  {p.unit ?? 'no unit'} · {p.sample_count.toLocaleString()} pts
                                </p>
                              </div>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
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
                      {!loadingChart && !chartError &&
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
                  {loadingChart && selectedParams.size > 0 && (
                    <div className="flex flex-col items-center justify-center h-64 gap-3 text-gray-400">
                      <RefreshCw className="w-5 h-5 animate-spin" />
                      <span className="text-sm">Loading chart data…</span>
                      <span className="text-xs text-gray-300">Large datasets may take a few seconds</span>
                    </div>
                  )}

                  {/* Chart error */}
                  {chartError && !loadingChart && (
                    <div className="flex items-center justify-center h-64 gap-3 text-red-500 text-sm">
                      <AlertCircle className="w-5 h-5 shrink-0" />
                      {chartError}
                    </div>
                  )}

                  {/* Time series chart */}
                  {!loadingChart && !chartError && seriesData.length > 0 && activeTab === 'timeseries' && (
                    <div ref={chartRef} className="bg-white">
                      <TimeSeriesChart
                        series={seriesData}
                        height={340}
                        showReferenceMean={showMean}
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
              {stats.length > 0 && !loadingChart && (
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
                        <CardDescription className="text-xs">
                          {s.statistics.count.toLocaleString()} data points
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
