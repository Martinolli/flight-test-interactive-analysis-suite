import { useState, useEffect } from 'react';
import { useLocation, useParams } from 'wouter';
import {
  ArrowLeft,
  Plane,
  Calendar,
  Clock,
  User,
  FileText,
  Edit,
  Trash2,
  AlertCircle,
  Info,
  Sparkles,
  Loader2,
  ChevronDown,
  ChevronUp,
  BarChart3,
  FileDown,
  Printer,
} from 'lucide-react';
import Sidebar from '../components/Sidebar';
import FlightTestModal from '../components/FlightTestModal';
import TimeSeriesChart, { TimeSeriesHoverSnapshot } from '../components/TimeSeriesChart';
import ParameterExplorerPanel from '../components/ParameterExplorerPanel';
import { ConfirmDialog } from '../components/ui/confirm-dialog';
import { ToastContainer, useToast } from '../components/ui/toast';
import {
  AIAnalysisResponse,
  AnalysisModeInfo,
  ApiService,
  DatasetVersion,
  FlightTest,
  ParameterInfo,
  ParameterSeries,
} from '../services/api';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { useAuth } from '../contexts/AuthContext';
import { cn } from '../lib/utils';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

function formatDateTime(dateString: string): string {
  return new Date(dateString).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return 'N/A';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function formatTimeCursor(timestamp: string): string {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) return timestamp;
  return parsed.toLocaleTimeString('en-US', { hour12: false });
}

function formatCursorValue(value: number | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

interface ParsedAnalysisContent {
  body: string;
  sources: string[];
  warnings: string[];
}

function parseAnalysisContent(analysisMarkdown: string): ParsedAnalysisContent {
  const referencesMatch = analysisMarkdown.match(/\n###\s+References\s*\n([\s\S]*)$/i);
  const body = (referencesMatch
    ? analysisMarkdown.slice(0, referencesMatch.index).trim()
    : analysisMarkdown
  ).trim();

  const sources: string[] = [];
  const warnings: string[] = [];

  if (referencesMatch?.[1]) {
    const referenceLines = referencesMatch[1]
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.startsWith('- '));

    for (const line of referenceLines) {
      const cleaned = line.replace(/^-+\s*/, '').trim();
      if (!cleaned) continue;
      if (cleaned.toLowerCase().includes('no inline [sx] citations')) {
        warnings.push(cleaned);
        continue;
      }
      sources.push(cleaned);
    }
  }

  return { body, sources, warnings };
}

type AnalysisModeKey =
  | 'takeoff'
  | 'landing'
  | 'performance'
  | 'handling_qualities'
  | 'buffet_vibration'
  | 'flutter'
  | 'propulsion_systems'
  | 'electrical_systems'
  | 'general';

interface QuickAnalysisPreset {
  label: string;
  mode: AnalysisModeKey;
  text: string;
}

const QUICK_ANALYSIS_PRESETS: QuickAnalysisPreset[] = [
  {
    label: 'Takeoff Performance',
    mode: 'takeoff',
    text: 'Analyse the takeoff performance: ground roll distance, rotation speed, climb gradient, and any deviations from expected values.',
  },
  {
    label: 'Landing Performance',
    mode: 'landing',
    text: 'Analyse the landing performance: approach speed, touchdown point, ground roll distance, and deceleration rate.',
  },
  {
    label: 'Climb Performance',
    mode: 'performance',
    text: 'Analyse the climb performance: rate of climb, climb gradient, engine parameters during climb, and fuel consumption.',
  },
  {
    label: 'Vibration & Loads',
    mode: 'buffet_vibration',
    text: 'Analyse structural loads and vibration data: identify any abnormal load factors, vibration frequencies, or exceedances of structural limits.',
  },
  {
    label: 'General Summary',
    mode: 'general',
    text: 'Produce a general flight test summary with executive overview, key parameter observations, anomalies, and recommendations.',
  },
];

function statusBadgeClasses(status?: string): string {
  switch (status) {
    case 'implemented':
      return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    case 'partial':
      return 'bg-amber-100 text-amber-800 border-amber-200';
    case 'planned':
      return 'bg-slate-100 text-slate-700 border-slate-200';
    case 'blocked':
      return 'bg-rose-100 text-rose-800 border-rose-200';
    default:
      return 'bg-gray-100 text-gray-700 border-gray-200';
  }
}

// ─── Parameters & Data Panel ─────────────────────────────────────────────────

function ParametersPanel({
  flightTestId,
  datasetVersionId,
  toast,
}: {
  flightTestId: number;
  datasetVersionId?: number;
  toast: ReturnType<typeof useToast>;
}) {
  const [parameters, setParameters] = useState<ParameterInfo[]>([]);
  const [selectedParams, setSelectedParams] = useState<Set<string>>(new Set());
  const [seriesData, setSeriesData] = useState<ParameterSeries[]>([]);
  const [hoverSnapshot, setHoverSnapshot] = useState<TimeSeriesHoverSnapshot | null>(null);
  const [loadingParams, setLoadingParams] = useState(true);
  const [loadingChart, setLoadingChart] = useState(false);
  const [paramsError, setParamsError] = useState('');

  useEffect(() => {
    setLoadingParams(true);
    setParamsError('');
    ApiService.getParametersForDataset(flightTestId, datasetVersionId)
      .then((params) => {
        setParameters(params);
        if (params.length > 0) {
          setSelectedParams(new Set([params[0].name]));
        }
      })
      .catch((err) => setParamsError(err instanceof Error ? err.message : 'Failed to load parameters'))
      .finally(() => setLoadingParams(false));
  }, [flightTestId, datasetVersionId]);

  useEffect(() => {
    if (selectedParams.size === 0) { setSeriesData([]); return; }
    setLoadingChart(true);
    ApiService.getParameterData(flightTestId, Array.from(selectedParams), datasetVersionId)
      .then(setSeriesData)
      .catch(() => setSeriesData([]))
      .finally(() => setLoadingChart(false));
  }, [flightTestId, selectedParams, datasetVersionId]);

  useEffect(() => {
    setHoverSnapshot(null);
  }, [selectedParams, datasetVersionId, flightTestId]);

  function toggleParam(name: string) {
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
  }

  function applyParameterSet(names: string[]) {
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
  }

  if (loadingParams) {
    return (
      <div className="flex items-center justify-center py-10 gap-2 text-gray-400">
        <Loader2 className="w-5 h-5 animate-spin" />
        <span className="text-sm">Loading parameters…</span>
      </div>
    );
  }

  if (paramsError) {
    return (
      <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
        <AlertCircle className="w-4 h-4 flex-shrink-0" />
        {paramsError}
      </div>
    );
  }

  if (parameters.length === 0) {
    return (
      <div className="border-2 border-dashed border-gray-200 rounded-lg p-8 text-center">
        <BarChart3 className="w-10 h-10 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-400 text-sm font-medium">No data uploaded yet</p>
        <p className="text-gray-400 text-xs mt-1">
          Upload a CSV file from the <strong>Upload Data</strong> page to see parameters here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">
        {parameters.length} parameter{parameters.length !== 1 ? 's' : ''} available
      </p>
      <ParameterExplorerPanel
        parameters={parameters}
        selectedParams={selectedParams}
        maxSelection={8}
        storageNamespace={`parameter-explorer:flight-test-${flightTestId}`}
        onToggleParam={toggleParam}
        onApplyParameterSet={applyParameterSet}
      />
      {selectedParams.size > 0 && (
        <div className="relative min-h-[280px]">
          {loadingChart ? (
            <div className="flex items-center justify-center py-10 gap-2 text-gray-400">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span className="text-sm">Loading chart data…</span>
            </div>
          ) : seriesData.length > 0 ? (
            <div className="space-y-2">
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
                series={seriesData}
                showReferenceMean={false}
                height={280}
                syncId={`flight-test-${flightTestId}-timeseries`}
                onHoverPoint={setHoverSnapshot}
              />
            </div>
          ) : (
            <div className="flex items-center justify-center py-10 text-gray-400 text-sm">
              No data points available for selected parameters.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── AI Analysis Panel ────────────────────────────────────────────────────────

function AIAnalysisPanel({
  flightTestId,
  datasetVersionId,
  datasetVersionLabel,
  datasetVersions,
  toast,
}: {
  flightTestId: number;
  datasetVersionId?: number;
  datasetVersionLabel?: string;
  datasetVersions: DatasetVersion[];
  toast: ReturnType<typeof useToast>;
}) {
  const [result, setResult] = useState<AIAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(true);
  const [showSources, setShowSources] = useState(false);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [loadingSavedJob, setLoadingSavedJob] = useState(false);
  const [savedJobIdInput, setSavedJobIdInput] = useState('');
  const [userPrompt, setUserPrompt] = useState('');
  const [selectedAnalysisMode, setSelectedAnalysisMode] = useState<AnalysisModeKey>('takeoff');
  const [analysisModes, setAnalysisModes] = useState<AnalysisModeInfo[]>([]);
  const [loadingAnalysisModes, setLoadingAnalysisModes] = useState(false);
  const { user } = useAuth();
  const parsedAnalysis = result ? parseAnalysisContent(result.analysis) : null;
  const analysisDatasetVersion =
    result?.dataset_version_id == null
      ? undefined
      : datasetVersions.find((v) => v.id === result.dataset_version_id);
  const analysisDatasetLabel =
    result?.dataset_version_id == null
      ? 'active/legacy'
      : (analysisDatasetVersion?.label ?? `v${result.dataset_version_id}`);
  const selectedDatasetLabel =
    datasetVersionLabel ?? (datasetVersionId == null ? 'none' : `v${datasetVersionId}`);
  const analysisDatasetDiffersFromSelection =
    result?.dataset_version_id != null &&
    datasetVersionId != null &&
    result.dataset_version_id !== datasetVersionId;
  const activeModeFromResult = (result?.analysis_mode ?? selectedAnalysisMode) as AnalysisModeKey;
  const selectedModeInfo =
    analysisModes.find((mode) => mode.key === selectedAnalysisMode) ??
    analysisModes.find((mode) => mode.default) ??
    null;

  useEffect(() => {
    let cancelled = false;
    setLoadingAnalysisModes(true);
    ApiService.getAnalysisModes()
      .then((modes) => {
        if (cancelled) return;
        setAnalysisModes(modes);
        const defaultMode = modes.find((mode) => mode.default)?.key as AnalysisModeKey | undefined;
        if (!selectedAnalysisMode && defaultMode) {
          setSelectedAnalysisMode(defaultMode);
        }
      })
      .catch(() => {
        if (cancelled) return;
        setAnalysisModes([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingAnalysisModes(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleExportPDF() {
    if (!result) return;
    if (!result.analysis_job_id) {
      toast.error('Missing analysis job ID for immutable PDF export.');
      return;
    }
    setExportingPdf(true);
    try {
      const blob = await ApiService.exportAnalysisPDF(flightTestId, result.analysis_job_id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `FTIAS_Report_${result.flight_test_name.replace(/\s+/g, '_')}_${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('PDF report downloaded.');
    } catch (err) {
      toast.error((err as Error).message || 'PDF export failed.');
    } finally {
      setExportingPdf(false);
    }
  }

  async function handlePrintPDF() {
    if (!result) return;
    if (!result.analysis_job_id) {
      toast.error('Missing analysis job ID for immutable PDF export.');
      return;
    }
    setExportingPdf(true);
    try {
      const blob = await ApiService.exportAnalysisPDF(flightTestId, result.analysis_job_id);
      const url = URL.createObjectURL(blob);
      const iframe = document.createElement('iframe');
      iframe.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;border:none;';
      iframe.src = url;
      document.body.appendChild(iframe);
      iframe.onload = () => {
        // Wait for the print dialog to open, then clean up only after it closes
        const cleanup = () => {
          document.body.removeChild(iframe);
          URL.revokeObjectURL(url);
          iframe.contentWindow?.removeEventListener('afterprint', cleanup);
        };
        // afterprint fires when the user dismisses the print dialog
        iframe.contentWindow?.addEventListener('afterprint', cleanup);
        // Fallback: if afterprint never fires (some browsers), clean up after 60s
        setTimeout(cleanup, 60_000);
        iframe.contentWindow?.focus();
        iframe.contentWindow?.print();
      };
    } catch (err) {
      toast.error((err as Error).message || 'Print failed.');
    } finally {
      setExportingPdf(false);
    }
  }

  async function runAnalysis() {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await ApiService.getAIAnalysis(
        flightTestId,
        userPrompt.trim() || undefined,
        datasetVersionId,
        selectedAnalysisMode
      );
      setResult(data);
      if (data.analysis_mode) {
        setSelectedAnalysisMode(data.analysis_mode as AnalysisModeKey);
      }
      setShowSources(false);
    } catch (err) {
      setError((err as Error).message || 'AI analysis failed');
    } finally {
      setLoading(false);
    }
  }

  async function loadSavedAnalysisJob() {
    const parsedId = Number(savedJobIdInput);
    if (!savedJobIdInput.trim() || Number.isNaN(parsedId) || parsedId <= 0) {
      toast.warning('Enter a valid analysis job ID.');
      return;
    }
    setLoadingSavedJob(true);
    setError('');
    try {
      const job = await ApiService.getAIAnalysisJob(flightTestId, parsedId);
      setResult({
        analysis: job.analysis,
        flight_test_name: job.flight_test_name,
        analysis_mode: job.analysis_mode ?? 'takeoff',
        capability_key: job.capability_key ?? null,
        dataset_version_id: job.dataset_version_id ?? null,
        parameters_analysed: job.parameters_analysed,
        analysis_job_id: job.id,
        model_name: job.model_name,
        model_version: job.model_version,
        output_sha256: job.output_sha256,
        created_at: job.created_at,
        retrieved_source_ids: job.retrieved_source_ids,
      });
      if (job.analysis_mode) {
        setSelectedAnalysisMode(job.analysis_mode as AnalysisModeKey);
      }
      setShowSources(false);
      toast.success(`Loaded analysis job #${job.id}`);
    } catch (err) {
      toast.error((err as Error).message || 'Failed to load saved analysis job.');
    } finally {
      setLoadingSavedJob(false);
    }
  }

  return (
    <Card className="mt-4 border-purple-200">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base text-purple-700">
            <Sparkles className="w-4 h-4" />
            AI Analysis
          </CardTitle>
          {result && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="text-gray-400 hover:text-gray-600"
            >
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          )}
        </div>
        <p className="text-xs text-gray-500 mt-1">
          Cross-references your flight data against indexed standards and handbooks using RAG.
        </p>
        {/* Mode + quick-prompt chips */}
        <div className="flex flex-wrap gap-1.5 mt-2">
          {QUICK_ANALYSIS_PRESETS.map((qp) => {
            const modeInfo = analysisModes.find((mode) => mode.key === qp.mode);
            const modeStatus = modeInfo?.capability_status;
            return (
            <button
              key={qp.label}
              onClick={() => {
                setSelectedAnalysisMode(qp.mode);
                setUserPrompt(qp.text);
              }}
              disabled={loading}
              className={cn(
                'text-xs px-2.5 py-1 rounded-full border transition-colors',
                selectedAnalysisMode === qp.mode
                  ? 'bg-purple-100 border-purple-300 text-purple-700'
                  : 'border-gray-200 text-gray-500 hover:border-purple-300 hover:text-purple-600'
              )}
              title={
                modeInfo
                  ? `${modeInfo.label} • ${modeInfo.capability_status} • ${modeInfo.authority}`
                  : qp.mode
              }
            >
              {qp.label}
              {modeStatus && modeStatus !== 'implemented' ? (
                <span className="ml-1 opacity-70">({modeStatus})</span>
              ) : null}
            </button>
            );
          })}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-gray-500">
            Selected mode: <strong>{selectedModeInfo?.label ?? selectedAnalysisMode}</strong>
          </span>
          {loadingAnalysisModes ? (
            <span className="inline-flex items-center gap-1 text-gray-400">
              <Loader2 className="h-3 w-3 animate-spin" />
              loading mode capabilities…
            </span>
          ) : selectedModeInfo ? (
            <>
              <span
                className={cn(
                  'inline-flex items-center rounded-full border px-2 py-0.5 font-medium capitalize',
                  statusBadgeClasses(selectedModeInfo.capability_status)
                )}
              >
                {selectedModeInfo.capability_status}
              </span>
              <span className="text-gray-500">{selectedModeInfo.authority}</span>
            </>
          ) : (
            <span className="text-amber-700">Mode catalog unavailable; backend default mode may apply.</span>
          )}
        </div>
        {selectedModeInfo && selectedModeInfo.capability_status !== 'implemented' && (
          <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            This mode is currently <strong>{selectedModeInfo.capability_status}</strong>. Results are bounded by
            capability limits and may return guidance/partial output instead of full deterministic analysis.
          </div>
        )}
      </CardHeader>
      <CardContent>
        {/* Prompt input — always visible */}
        <div className="mb-4">
          <textarea
            value={userPrompt}
            onChange={(e) => setUserPrompt(e.target.value)}
            placeholder="Describe your analysis goal for the selected mode, or click a chip above to pre-fill… (leave blank to use mode-default behavior)"
            rows={2}
            disabled={loading}
            className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800
                       placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-400
                       focus:border-transparent resize-none disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>

        <div className="mb-4 rounded-lg border border-gray-200 bg-gray-50 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-600 mb-2">
            Re-open Saved Analysis by ID
          </p>
          <div className="flex gap-2">
            <input
              type="number"
              min={1}
              placeholder="Analysis Job ID"
              value={savedJobIdInput}
              onChange={(e) => setSavedJobIdInput(e.target.value)}
              className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800
                         placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-400
                         focus:border-transparent"
            />
            <Button
              variant="outline"
              onClick={loadSavedAnalysisJob}
              disabled={loadingSavedJob}
              className="shrink-0"
            >
              {loadingSavedJob ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Open'}
            </Button>
          </div>
        </div>

        {!result && !loading && !error && (
          <div className="text-center py-4">
            <Button
              onClick={runAnalysis}
              className="bg-purple-600 hover:bg-purple-700 text-white"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              Analyse with AI
            </Button>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-8 gap-3">
            <Loader2 className="w-5 h-5 animate-spin text-purple-600" />
            <span className="text-sm text-gray-600">
              Retrieving relevant standards and generating analysis…
            </span>
          </div>
        )}

        {error && (
          <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm text-red-700">{error}</p>
              <button
                onClick={runAnalysis}
                className="text-xs text-red-600 underline mt-1"
              >
                Try again
              </button>
            </div>
          </div>
        )}

        {result && expanded && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-xs text-gray-500 pb-2 border-b border-gray-100">
              <span>{result.parameters_analysed} parameters analysed</span>
              <span>·</span>
              <span>Flight test: {result.flight_test_name}</span>
              <span>·</span>
              <span>Mode: {result.analysis_mode ?? activeModeFromResult}</span>
              <span>·</span>
              <span>Analysis dataset: {analysisDatasetLabel}</span>
              <span>·</span>
              <span>Analysis Job #{result.analysis_job_id}</span>
            </div>
            {result.analysis_mode && result.analysis_mode !== selectedAnalysisMode && (
              <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-800">
                Loaded analysis was generated in mode <strong>{result.analysis_mode}</strong>, while current
                selection is <strong>{selectedAnalysisMode}</strong>.
              </div>
            )}
            {analysisDatasetDiffersFromSelection && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                Reopened analysis provenance uses <strong>{analysisDatasetLabel}</strong>, while
                current page selection is <strong>{selectedDatasetLabel}</strong>.
              </div>
            )}

            <div className="max-h-[65vh] min-h-[240px] overflow-y-auto rounded-xl border border-purple-100 bg-purple-50/40 p-3 pr-1">
              <div className="flex justify-start">
                <div className="w-full rounded-2xl rounded-tl-sm border border-gray-200 bg-white px-4 py-3 shadow-sm">
                  <div className="mb-2 flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5 text-purple-500" />
                    <span className="text-xs font-medium text-purple-600">AI Analysis</span>
                  </div>
                  <div
                    className="
                      prose prose-sm max-w-none
                      prose-headings:font-semibold prose-headings:text-gray-800
                      prose-p:text-gray-700 prose-p:leading-relaxed
                      prose-strong:text-gray-900
                      prose-ul:my-2 prose-ol:my-2
                      prose-table:text-xs prose-table:w-full
                      prose-th:bg-gray-50 prose-th:px-3 prose-th:py-2 prose-th:text-left prose-th:font-semibold prose-th:text-gray-700 prose-th:border prose-th:border-gray-200
                      prose-td:px-3 prose-td:py-1.5 prose-td:border prose-td:border-gray-200 prose-td:text-gray-700 prose-td:align-top
                      prose-tr:even:bg-gray-50
                      prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded prose-code:text-xs
                      prose-pre:bg-gray-900 prose-pre:text-gray-100 prose-pre:rounded-lg prose-pre:p-3
                      prose-blockquote:border-l-purple-300 prose-blockquote:text-gray-600
                    "
                  >
                    <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
                      {parsedAnalysis?.body || result.analysis}
                    </ReactMarkdown>
                  </div>

                  {(parsedAnalysis?.warnings.length ?? 0) > 0 && (
                    <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-2.5">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700 mb-1">
                        Quality Notice
                      </p>
                      <div className="space-y-0.5">
                        {parsedAnalysis?.warnings.map((warning) => (
                          <p key={warning} className="text-xs text-amber-800">
                            - {warning}
                          </p>
                        ))}
                      </div>
                    </div>
                  )}

                  {(parsedAnalysis?.sources.length ?? 0) > 0 && (
                    <div className="mt-3 border-t border-gray-100 pt-3">
                      <button
                        onClick={() => setShowSources((v) => !v)}
                        className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 transition-colors"
                      >
                        <FileText className="w-3.5 h-3.5" />
                        {parsedAnalysis?.sources.length} source{(parsedAnalysis?.sources.length ?? 0) > 1 ? 's' : ''}
                        {showSources ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                      </button>
                      {showSources && (
                        <div className="mt-2 space-y-1.5">
                          {parsedAnalysis?.sources.map((source) => (
                            <div key={source} className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-700">
                              {source}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={runAnalysis}
                  disabled={loading}
                  className="text-purple-600 border-purple-200 hover:bg-purple-50"
                >
                  <Sparkles className="w-3 h-3 mr-1" />
                  Re-run
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => { setResult(null); setError(''); setUserPrompt(''); }}
                  className="text-gray-500 border-gray-200 hover:bg-gray-50"
                >
                  New Query
                </Button>
              </div>
              {user?.is_superuser && (
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleExportPDF}
                    disabled={exportingPdf}
                    className="text-blue-600 border-blue-200 hover:bg-blue-50"
                  >
                    {exportingPdf ? (
                      <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                    ) : (
                      <FileDown className="w-3 h-3 mr-1" />
                    )}
                    Download PDF
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePrintPDF}
                    disabled={exportingPdf}
                    className="text-gray-600 border-gray-200 hover:bg-gray-50"
                  >
                    <Printer className="w-3 h-3 mr-1" />
                    Print
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function FlightTestDetail() {
  const { id } = useParams<{ id: string }>();
  const [, setLocation] = useLocation();
  const toast = useToast();

  const [flightTest, setFlightTest] = useState<FlightTest | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [datasetVersions, setDatasetVersions] = useState<DatasetVersion[]>([]);
  const [loadingDatasetVersions, setLoadingDatasetVersions] = useState(false);
  const [selectedDatasetVersionId, setSelectedDatasetVersionId] = useState<number | ''>('');
  const [activatingDataset, setActivatingDataset] = useState(false);

  useEffect(() => {
    if (id) loadFlightTest(Number(id));
  }, [id]);

  const loadDatasetVersions = async (testId: number, activeDatasetVersionId?: number | null) => {
    setLoadingDatasetVersions(true);
    try {
      const versions = await ApiService.getDatasetVersions(testId);
      setDatasetVersions(versions);
      const preferred =
        versions.find((v) => v.id === activeDatasetVersionId)?.id ??
        versions.find((v) => v.is_active)?.id ??
        versions.find((v) => v.status === 'success')?.id;
      setSelectedDatasetVersionId(preferred ?? '');
    } catch (err) {
      setDatasetVersions([]);
      setSelectedDatasetVersionId('');
      toast.warning(
        'Could not load dataset versions',
        err instanceof Error ? err.message : 'Dataset versions are unavailable'
      );
    } finally {
      setLoadingDatasetVersions(false);
    }
  };

  const loadFlightTest = async (testId: number) => {
    try {
      setIsLoading(true);
      setError('');
      const test = await ApiService.getFlightTest(testId);
      setFlightTest(test);
      await loadDatasetVersions(testId, test.active_dataset_version_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load flight test');
    } finally {
      setIsLoading(false);
    }
  };

  const handleEditSuccess = (updated: FlightTest) => {
    setFlightTest(updated);
    toast.success('Flight test updated', 'Changes have been saved successfully.');
  };

  const handleDelete = async () => {
    if (!flightTest) return;
    setIsDeleting(true);
    try {
      await ApiService.deleteFlightTest(flightTest.id);
      toast.success('Flight test deleted', 'The record has been removed.');
      setTimeout(() => setLocation('/'), 800);
    } catch (err) {
      toast.error(
        'Delete failed',
        err instanceof Error ? err.message : 'Could not delete the flight test.'
      );
      setIsDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  const selectedDatasetVersion =
    selectedDatasetVersionId === ''
      ? undefined
      : datasetVersions.find((v) => v.id === Number(selectedDatasetVersionId));
  const activeDatasetVersion = datasetVersions.find((v) => v.is_active);

  const handleActivateDatasetVersion = async () => {
    if (!flightTest || selectedDatasetVersionId === '') return;
    const versionId = Number(selectedDatasetVersionId);
    setActivatingDataset(true);
    try {
      const updated = await ApiService.activateDatasetVersion(flightTest.id, versionId);
      setFlightTest(updated);
      await loadDatasetVersions(flightTest.id, updated.active_dataset_version_id);
      toast.success(
        `Active dataset set to ${selectedDatasetVersion?.label ?? `v${versionId}`}`
      );
    } catch (err) {
      toast.error(
        'Failed to activate dataset',
        err instanceof Error ? err.message : 'Could not set active dataset version.'
      );
    } finally {
      setActivatingDataset(false);
    }
  };

  return (
    <Sidebar>
      <div className="mx-auto w-full max-w-[1400px] p-4 sm:p-6 lg:p-8">
        {/* Back button */}
        <button
          onClick={() => setLocation('/')}
          className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-800 transition-colors mb-6 group"
        >
          <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          Back to Flight Tests
        </button>

        {/* Loading */}
        {isLoading && (
          <div className="flex items-center justify-center py-24">
            <div className="text-center">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4" />
              <p className="text-gray-500">Loading flight test...</p>
            </div>
          </div>
        )}

        {/* Error */}
        {error && !isLoading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center">
              <AlertCircle className="w-8 h-8 text-red-400" />
            </div>
            <div className="text-center">
              <h3 className="text-lg font-medium text-gray-900 mb-1">Failed to load</h3>
              <p className="text-gray-500 text-sm">{error}</p>
            </div>
            <Button variant="outline" onClick={() => loadFlightTest(Number(id))}>
              Try Again
            </Button>
          </div>
        )}

        {/* Content */}
        {!isLoading && !error && flightTest && (
          <>
            {/* Header */}
            <div className="flex items-start justify-between mb-8">
              <div className="flex items-start gap-4">
                <div className="w-14 h-14 bg-blue-100 rounded-xl flex items-center justify-center shrink-0">
                  <Plane className="w-7 h-7 text-blue-600" />
                </div>
                <div>
                  <div className="flex items-center gap-3 mb-1">
                    <h1 className="text-2xl font-bold text-gray-900">{flightTest.test_name}</h1>
                    <Badge variant="secondary">#{flightTest.id}</Badge>
                  </div>
                  <p className="text-gray-500 text-sm">{flightTest.aircraft_type}</p>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex gap-2 shrink-0">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowEditModal(true)}
                  className="gap-2"
                >
                  <Edit className="w-4 h-4" />
                  Edit
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowDeleteConfirm(true)}
                  className="gap-2 text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200 hover:border-red-300"
                >
                  <Trash2 className="w-4 h-4" />
                  Delete
                </Button>
              </div>
            </div>

            {/* Metadata Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
              <Card>
                <CardContent className="flex items-center gap-4 pt-6">
                  <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center shrink-0">
                    <Calendar className="w-5 h-5 text-blue-500" />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Test Date</p>
                    <p className="text-sm font-semibold text-gray-900 mt-0.5">
                      {formatDate(flightTest.test_date)}
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="flex items-center gap-4 pt-6">
                  <div className="w-10 h-10 bg-purple-50 rounded-lg flex items-center justify-center shrink-0">
                    <Clock className="w-5 h-5 text-purple-500" />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Duration</p>
                    <p className="text-sm font-semibold text-gray-900 mt-0.5">
                      {formatDuration(flightTest.duration_seconds)}
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="flex items-center gap-4 pt-6">
                  <div className="w-10 h-10 bg-green-50 rounded-lg flex items-center justify-center shrink-0">
                    <User className="w-5 h-5 text-green-500" />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Created By</p>
                    <p className="text-sm font-semibold text-gray-900 mt-0.5">
                      User #{flightTest.created_by_id}
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="flex items-center gap-4 pt-6">
                  <div className="w-10 h-10 bg-orange-50 rounded-lg flex items-center justify-center shrink-0">
                    <FileText className="w-5 h-5 text-orange-500" />
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">Last Updated</p>
                    <p className="text-sm font-semibold text-gray-900 mt-0.5">
                      {flightTest.updated_at
                        ? formatDateTime(flightTest.updated_at)
                        : formatDateTime(flightTest.created_at)}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Description */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Description</CardTitle>
              </CardHeader>
              <CardContent>
                {flightTest.description ? (
                  <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-wrap">
                    {flightTest.description}
                  </p>
                ) : (
                  <p className="text-gray-400 text-sm italic">No description provided.</p>
                )}
              </CardContent>
            </Card>

            <Card className="mt-4">
              <CardHeader>
                <CardTitle className="text-base">Dataset Version</CardTitle>
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
                    : 'No active dataset set yet for this flight test.'}
                </p>
              </CardContent>
            </Card>

            <Card className="mt-4 border-amber-200 bg-amber-50/60">
              <CardContent className="pt-5">
                <div className="flex gap-3">
                  <Info className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                  <div className="space-y-1 text-sm text-amber-900">
                    <p className="font-semibold">Dataset scope</p>
                    <p>
                      Parameters & Data and Analyze with AI use the{' '}
                      <strong>selected dataset version</strong>.
                    </p>
                    <p>
                      Current selection:{' '}
                      <strong>{selectedDatasetVersion?.label ?? 'none'}</strong>. Activate a
                      selected version to make it the default dataset for this flight test.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Parameters & Data */}
            <Card className="mt-4">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <BarChart3 className="w-4 h-4 text-blue-500" />
                  Parameters & Data
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ParametersPanel
                  flightTestId={flightTest.id}
                  datasetVersionId={
                    selectedDatasetVersionId === '' ? undefined : Number(selectedDatasetVersionId)
                  }
                  toast={toast}
                />
              </CardContent>
            </Card>

            {/* AI Analysis panel */}
            <AIAnalysisPanel
              flightTestId={flightTest.id}
              datasetVersionId={
                selectedDatasetVersionId === '' ? undefined : Number(selectedDatasetVersionId)
              }
              datasetVersionLabel={selectedDatasetVersion?.label}
              datasetVersions={datasetVersions}
              toast={toast}
            />
          </>
        )}
      </div>

      {/* Edit Modal */}
      {flightTest && (
        <FlightTestModal
          open={showEditModal}
          onClose={() => setShowEditModal(false)}
          onSuccess={handleEditSuccess}
          editingTest={flightTest}
        />
      )}

      {/* Delete Confirmation */}
      <ConfirmDialog
        open={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={handleDelete}
        title="Delete Flight Test"
        description={`Are you sure you want to delete "${flightTest?.test_name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        isLoading={isDeleting}
      />

      {/* Toasts */}
      <ToastContainer toasts={toast.toasts} onDismiss={toast.dismiss} />
    </Sidebar>
  );
}
