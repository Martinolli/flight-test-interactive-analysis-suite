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
  Sparkles,
  Loader2,
  BookOpen,
  ChevronDown,
  ChevronUp,
  BarChart3,
  FileDown,
  Printer,
} from 'lucide-react';
import Sidebar from '../components/Sidebar';
import FlightTestModal from '../components/FlightTestModal';
import TimeSeriesChart from '../components/TimeSeriesChart';
import { ConfirmDialog } from '../components/ui/confirm-dialog';
import { ToastContainer, useToast } from '../components/ui/toast';
import { ApiService, FlightTest, AIAnalysisResponse, ParameterInfo, ParameterSeries } from '../services/api';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { useAuth } from '../contexts/AuthContext';
import { cn } from '../lib/utils';

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

// ─── Parameters & Data Panel ─────────────────────────────────────────────────

function ParametersPanel({ flightTestId }: { flightTestId: number }) {
  const [parameters, setParameters] = useState<ParameterInfo[]>([]);
  const [selectedParams, setSelectedParams] = useState<Set<string>>(new Set());
  const [seriesData, setSeriesData] = useState<ParameterSeries[]>([]);
  const [loadingParams, setLoadingParams] = useState(true);
  const [loadingChart, setLoadingChart] = useState(false);
  const [paramsError, setParamsError] = useState('');

  useEffect(() => {
    setLoadingParams(true);
    setParamsError('');
    ApiService.getParameters(flightTestId)
      .then((params) => {
        setParameters(params);
        if (params.length > 0) {
          setSelectedParams(new Set([params[0].name]));
        }
      })
      .catch((err) => setParamsError(err instanceof Error ? err.message : 'Failed to load parameters'))
      .finally(() => setLoadingParams(false));
  }, [flightTestId]);

  useEffect(() => {
    if (selectedParams.size === 0) { setSeriesData([]); return; }
    setLoadingChart(true);
    ApiService.getParameterData(flightTestId, Array.from(selectedParams))
      .then(setSeriesData)
      .catch(() => setSeriesData([]))
      .finally(() => setLoadingChart(false));
  }, [flightTestId, selectedParams]);

  function toggleParam(name: string) {
    setSelectedParams((prev) => {
      const next = new Set(prev);
      if (next.has(name)) { next.delete(name); } else { next.add(name); }
      return next;
    });
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
          Upload a CSV or Excel file from the <strong>Upload Data</strong> page to see parameters here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">
        {parameters.length} parameter{parameters.length !== 1 ? 's' : ''} available — select to plot
      </p>
      <div className="flex flex-wrap gap-2">
        {parameters.map((p) => (
          <button
            key={p.name}
            onClick={() => toggleParam(p.name)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
              selectedParams.has(p.name)
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'
            }`}
          >
            {p.name}{p.unit ? ` (${p.unit})` : ''}
          </button>
        ))}
      </div>
      {selectedParams.size > 0 && (
        <div className="relative min-h-[280px]">
          {loadingChart ? (
            <div className="flex items-center justify-center py-10 gap-2 text-gray-400">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span className="text-sm">Loading chart data…</span>
            </div>
          ) : seriesData.length > 0 ? (
            <TimeSeriesChart series={seriesData} showReferenceMean={false} height={280} />
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
  toast,
}: {
  flightTestId: number;
  toast: ReturnType<typeof useToast>;
}) {
  const [result, setResult] = useState<AIAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(true);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [userPrompt, setUserPrompt] = useState('');
  const { user } = useAuth();

  // Quick-prompt chips — click to pre-fill the prompt box
  const QUICK_PROMPTS = [
    { label: 'Takeoff Performance', text: 'Analyse the takeoff performance: ground roll distance, rotation speed, climb gradient, and any deviations from expected values.' },
    { label: 'Landing Performance', text: 'Analyse the landing performance: approach speed, touchdown point, ground roll distance, and deceleration rate.' },
    { label: 'Climb Performance', text: 'Analyse the climb performance: rate of climb, climb gradient, engine parameters during climb, and fuel consumption.' },
    { label: 'Vibration & Loads', text: 'Analyse structural loads and vibration data: identify any abnormal load factors, vibration frequencies, or exceedances of structural limits.' },
    { label: 'General Summary', text: 'Produce a general flight test summary with executive overview, key parameter observations, anomalies, and recommendations.' },
  ];

  async function handleExportPDF() {
    if (!result) return;
    setExportingPdf(true);
    try {
      const blob = await ApiService.exportAnalysisPDF(flightTestId, result.analysis);
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
    setExportingPdf(true);
    try {
      const blob = await ApiService.exportAnalysisPDF(flightTestId, result.analysis);
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
      const data = await ApiService.getAIAnalysis(flightTestId, userPrompt.trim() || undefined);
      setResult(data);
    } catch (err) {
      setError((err as Error).message || 'AI analysis failed');
    } finally {
      setLoading(false);
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
        {/* Quick-prompt chips */}
        <div className="flex flex-wrap gap-1.5 mt-2">
          {QUICK_PROMPTS.map((qp) => (
            <button
              key={qp.label}
              onClick={() => setUserPrompt(qp.text)}
              disabled={loading}
              className={cn(
                'text-xs px-2.5 py-1 rounded-full border transition-colors',
                userPrompt === qp.text
                  ? 'bg-purple-100 border-purple-300 text-purple-700'
                  : 'border-gray-200 text-gray-500 hover:border-purple-300 hover:text-purple-600'
              )}
            >
              {qp.label}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {/* Prompt input — always visible */}
        <div className="mb-4">
          <textarea
            value={userPrompt}
            onChange={(e) => setUserPrompt(e.target.value)}
            placeholder="Describe your analysis goal, or click a chip above to pre-fill… (leave blank for a general report)"
            rows={2}
            disabled={loading}
            className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800
                       placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-400
                       focus:border-transparent resize-none disabled:opacity-50 disabled:cursor-not-allowed"
          />
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
            </div>

            <div className="prose prose-sm max-w-none">
              <pre className="whitespace-pre-wrap font-sans text-sm text-gray-800 leading-relaxed">
                {result.analysis}
              </pre>
            </div>

            <div className="flex items-center justify-between pt-2 flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={runAnalysis}
                className="text-purple-600 border-purple-200 hover:bg-purple-50"
              >
                <Sparkles className="w-3 h-3 mr-1" />
                Re-run Analysis
              </Button>
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

  useEffect(() => {
    if (id) loadFlightTest(Number(id));
  }, [id]);

  const loadFlightTest = async (testId: number) => {
    try {
      setIsLoading(true);
      setError('');
      const test = await ApiService.getFlightTest(testId);
      setFlightTest(test);
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

  return (
    <Sidebar>
      <div className="p-8 max-w-4xl">
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

            {/* Parameters & Data */}
            <Card className="mt-4">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <BarChart3 className="w-4 h-4 text-blue-500" />
                  Parameters & Data
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ParametersPanel flightTestId={flightTest.id} />
              </CardContent>
            </Card>

            {/* AI Analysis panel */}
            <AIAnalysisPanel flightTestId={flightTest.id} toast={toast} />
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
