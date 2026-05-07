import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  FileDown,
  Loader2,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import Sidebar from '../components/Sidebar';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { ToastContainer, useToast } from '../components/ui/toast';
import {
  ApiService,
  DatasetVersion,
  FlightTest,
  FratAnalysisJobReference,
  FratAssessment,
} from '../services/api';

type CategoryKey =
  | 'mission_profile'
  | 'weather_environment'
  | 'runway_operational'
  | 'aircraft_system_status'
  | 'crew_readiness';

interface CategoryState {
  score: number;
  notes: string;
}

interface FratFormState {
  assessmentName: string;
  datasetVersionId: number | '';
  selectedAnalysisJobIds: Set<number>;
  categories: Record<CategoryKey, CategoryState>;
  manualAdjustment: number;
  criticalFlags: {
    critical_system_unavailable: boolean;
    mandatory_data_missing: boolean;
    crew_unfit: boolean;
  };
  requestedDecisionAuthority: 'authoritative' | 'advisory';
  reviewerNotes: string;
  overrideNote: string;
  transitionNotes: string;
}

const CATEGORY_FIELDS: Array<{ key: CategoryKey; label: string }> = [
  { key: 'mission_profile', label: 'Mission / Test Profile' },
  { key: 'weather_environment', label: 'Weather / Environment' },
  { key: 'runway_operational', label: 'Runway / Operational' },
  { key: 'aircraft_system_status', label: 'Aircraft / System Status' },
  { key: 'crew_readiness', label: 'Crew Readiness' },
];

const CATEGORY_GUIDANCE: Record<CategoryKey, string> = {
  mission_profile:
    'Complexity of the planned mission/test profile. Higher values mean more demanding objectives, envelope expansion, or abnormal procedures.',
  weather_environment:
    'Weather, visibility, turbulence, temperature, winds, and environmental margins affecting the mission.',
  runway_operational:
    'Runway, airspace, range, traffic, NOTAM, recovery, and operational constraints.',
  aircraft_system_status:
    'Aircraft configuration, maintenance status, deferred defects, instrumentation, and system readiness.',
  crew_readiness:
    'Crew currency, workload, fatigue, briefing quality, and readiness for the planned profile.',
};

const FIELD_GUIDANCE = {
  assessmentName: 'Use a recognizable mission window, test card, sortie, or review name.',
  datasetVersion:
    'Selects the dataset version this FRAT assessment references. The saved assessment keeps this provenance.',
  requestedAuthority:
    'Authoritative support is intended for formal review. Advisory support records risk context without implying approval authority.',
  manualAdjustment:
    'Optional -10 to +10 reviewer adjustment. Use sparingly and document the rationale when non-zero.',
  linkedAnalysis:
    'Attach saved AI/engineering analysis jobs so technical evidence can contribute to the FRAT explanation and score composition.',
  reviewNotes:
    'General reasoning, reviewer observations, and risk-basis comments. Recommended for moderate or higher risk.',
  overrideNote:
    'Rationale for manual adjustments or formal acceptance decisions. Recommended when manual adjustment is not zero.',
  transitionNotes:
    'Notes recorded with approval, rejection, or finalization actions. Explain why the lifecycle state changed.',
};

const HARD_STOP_GUIDANCE: Record<keyof FratFormState['criticalFlags'], string> = {
  critical_system_unavailable:
    'Select when a required aircraft, safety, instrumentation, or mission-critical system is unavailable.',
  mandatory_data_missing:
    'Select when required evidence or dataset coverage is missing for the decision being requested.',
  crew_unfit:
    'Select when crew readiness, medical, currency, fatigue, or qualification concerns prevent safe continuation.',
};

const HARD_STOP_LABELS: Record<keyof FratFormState['criticalFlags'], string> = {
  critical_system_unavailable: 'Critical system unavailable',
  mandatory_data_missing: 'Mandatory data missing',
  crew_unfit: 'Crew unfit',
};

const SCORE_GUIDE = [
  ['0-4', 'Minimal', 'Normal condition, no meaningful added risk'],
  ['5-8', 'Low', 'Minor concern, manageable with standard controls'],
  ['9-12', 'Moderate', 'Noticeable risk contributor, requires awareness/monitoring'],
  ['13-16', 'High', 'Significant risk contributor, mitigation/review required'],
  ['17-20', 'Critical', 'Severe contributor, escalation or no-go unless formally accepted'],
];

function createDefaultFormState(): FratFormState {
  return {
    assessmentName: '',
    datasetVersionId: '',
    selectedAnalysisJobIds: new Set<number>(),
    categories: {
      mission_profile: { score: 0, notes: '' },
      weather_environment: { score: 0, notes: '' },
      runway_operational: { score: 0, notes: '' },
      aircraft_system_status: { score: 0, notes: '' },
      crew_readiness: { score: 0, notes: '' },
    },
    manualAdjustment: 0,
    criticalFlags: {
      critical_system_unavailable: false,
      mandatory_data_missing: false,
      crew_unfit: false,
    },
    requestedDecisionAuthority: 'authoritative',
    reviewerNotes: '',
    overrideNote: '',
    transitionNotes: '',
  };
}

function statusClasses(status: string): string {
  switch (status) {
    case 'finalized':
      return 'bg-emerald-100 text-emerald-800 border-emerald-200';
    case 'approved':
      return 'bg-blue-100 text-blue-800 border-blue-200';
    case 'rejected':
      return 'bg-rose-100 text-rose-800 border-rose-200';
    case 'needs_review':
      return 'bg-amber-100 text-amber-800 border-amber-200';
    case 'scored':
      return 'bg-purple-100 text-purple-800 border-purple-200';
    default:
      return 'bg-gray-100 text-gray-700 border-gray-200';
  }
}

function riskBandClasses(riskBand?: string): string {
  switch (riskBand) {
    case 'low':
      return 'text-emerald-700';
    case 'moderate':
      return 'text-amber-700';
    case 'high':
      return 'text-orange-700';
    case 'unacceptable':
      return 'text-rose-700';
    default:
      return 'text-gray-600';
  }
}

function normalizeNumber(value: string, min: number, max: number): number {
  const parsed = Number(value);
  if (Number.isNaN(parsed)) return min;
  return Math.min(max, Math.max(min, Math.round(parsed)));
}

function formatDateTime(value?: string | null): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function workflowStatusMessage({
  status,
  hasScore,
  hasHardStop,
  canExport,
}: {
  status: string;
  hasScore: boolean;
  hasHardStop: boolean;
  canExport: boolean;
}): string {
  if (status === 'finalized') return 'Finalized: immutable final artifact. Export remains available for traceability.';
  if (status === 'rejected') return 'Rejected / No-Go: export remains available for traceability and review records.';
  if (status === 'approved') return 'Approved: review transition notes and finalize when the decision is ready to lock.';
  if (status === 'needs_review') return 'Needs review: resolve risk drivers, document rationale, then approve or reject.';
  if (status === 'scored') {
    return hasHardStop
      ? 'Scored with hard-stop active: resolve or formally reject/no-go. Low numeric score does not cancel a hard-stop.'
      : 'Scored: review score composition, notes, and approve or reject.';
  }
  if (!hasScore) return 'Draft: complete inputs, save the draft, then score the assessment.';
  return canExport ? 'Scored assessment: export is available.' : 'Select or score an assessment to continue.';
}

export default function Frat() {
  const toast = useToast();

  const [flightTests, setFlightTests] = useState<FlightTest[]>([]);
  const [selectedFlightTestId, setSelectedFlightTestId] = useState<number | ''>('');
  const [datasetVersions, setDatasetVersions] = useState<DatasetVersion[]>([]);
  const [analysisJobs, setAnalysisJobs] = useState<FratAnalysisJobReference[]>([]);
  const [assessments, setAssessments] = useState<FratAssessment[]>([]);
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<number | ''>('');
  const [assessmentIdLookup, setAssessmentIdLookup] = useState('');
  const [form, setForm] = useState<FratFormState>(createDefaultFormState());

  const [loadingTests, setLoadingTests] = useState(true);
  const [loadingContext, setLoadingContext] = useState(false);
  const [saving, setSaving] = useState(false);
  const [scoring, setScoring] = useState(false);
  const [transitioning, setTransitioning] = useState(false);
  const [exporting, setExporting] = useState(false);

  const selectedAssessment = useMemo(
    () => assessments.find((item) => item.id === selectedAssessmentId),
    [assessments, selectedAssessmentId]
  );
  const selectedFlightTestName =
    flightTests.find((item) => item.id === selectedFlightTestId)?.test_name ?? 'N/A';
  const selectedAssessmentStatus = selectedAssessment?.status ?? 'draft';
  const canEdit = selectedAssessmentStatus !== 'finalized';

  useEffect(() => {
    ApiService.getFlightTests()
      .then((items) => {
        setFlightTests(items);
        const preferred = items[0]?.id;
        if (preferred) setSelectedFlightTestId(preferred);
      })
      .catch((err) => {
        toast.error('Could not load flight tests', err instanceof Error ? err.message : undefined);
      })
      .finally(() => setLoadingTests(false));
  }, []);

  useEffect(() => {
    if (selectedFlightTestId === '') {
      setDatasetVersions([]);
      setAnalysisJobs([]);
      setAssessments([]);
      setSelectedAssessmentId('');
      setForm(createDefaultFormState());
      return;
    }
    void refreshFlightTestContext(Number(selectedFlightTestId));
  }, [selectedFlightTestId]);

  async function refreshFlightTestContext(flightTestId: number) {
    setLoadingContext(true);
    try {
      const [versions, jobs, fratAssessments] = await Promise.all([
        ApiService.getDatasetVersions(flightTestId),
        ApiService.getFlightTestAnalysisJobs(flightTestId),
        ApiService.getFratAssessments(flightTestId),
      ]);
      setDatasetVersions(versions);
      setAnalysisJobs(jobs);
      setAssessments(fratAssessments);

      if (selectedAssessmentId !== '' && fratAssessments.some((item) => item.id === selectedAssessmentId)) {
        const refreshed = fratAssessments.find((item) => item.id === selectedAssessmentId);
        if (refreshed) hydrateFormFromAssessment(refreshed);
      } else if (fratAssessments[0]) {
        setSelectedAssessmentId(fratAssessments[0].id);
        hydrateFormFromAssessment(fratAssessments[0]);
      } else {
        setSelectedAssessmentId('');
        const defaultState = createDefaultFormState();
        const activeVersionId = versions.find((item) => item.is_active)?.id;
        if (activeVersionId) defaultState.datasetVersionId = activeVersionId;
        setForm(defaultState);
      }
    } catch (err) {
      toast.error(
        'Could not load FRAT context',
        err instanceof Error ? err.message : 'Failed to load dataset versions / assessments'
      );
    } finally {
      setLoadingContext(false);
    }
  }

  function hydrateFormFromAssessment(assessment: FratAssessment) {
    const next = createDefaultFormState();
    next.assessmentName = assessment.assessment_name ?? '';
    next.datasetVersionId = assessment.dataset_version_id ?? '';
    next.selectedAnalysisJobIds = new Set(assessment.analysis_reference_ids ?? []);

    const categorySnapshot = assessment.input_snapshot?.categories ?? {};
    for (const field of CATEGORY_FIELDS) {
      const source = categorySnapshot[field.key] ?? {};
      next.categories[field.key] = {
        score: typeof source.score === 'number' ? source.score : 0,
        notes: source.notes ?? '',
      };
    }

    next.manualAdjustment =
      typeof assessment.input_snapshot?.manual_adjustment === 'number'
        ? assessment.input_snapshot.manual_adjustment
        : 0;
    next.criticalFlags = {
      critical_system_unavailable: !!assessment.input_snapshot?.critical_flags?.critical_system_unavailable,
      mandatory_data_missing: !!assessment.input_snapshot?.critical_flags?.mandatory_data_missing,
      crew_unfit: !!assessment.input_snapshot?.critical_flags?.crew_unfit,
    };
    next.requestedDecisionAuthority =
      assessment.input_snapshot?.requested_decision_authority === 'advisory'
        ? 'advisory'
        : 'authoritative';
    next.reviewerNotes = assessment.input_snapshot?.reviewer_notes ?? '';
    next.overrideNote = assessment.input_snapshot?.override_note ?? '';
    next.transitionNotes = assessment.approval_notes ?? '';
    setForm(next);
  }

  function buildInputsPayload() {
    return {
      categories: CATEGORY_FIELDS.reduce(
        (acc, field) => {
          acc[field.key] = {
            score: form.categories[field.key].score,
            notes: form.categories[field.key].notes,
          };
          return acc;
        },
        {} as Record<CategoryKey, CategoryState>
      ),
      manual_adjustment: form.manualAdjustment,
      critical_flags: {
        ...form.criticalFlags,
      },
      requested_decision_authority: form.requestedDecisionAuthority,
      reviewer_notes: form.reviewerNotes,
      override_note: form.overrideNote,
    };
  }

  function updateAssessmentList(updated: FratAssessment) {
    setAssessments((prev) => {
      const next = [...prev];
      const idx = next.findIndex((item) => item.id === updated.id);
      if (idx >= 0) next[idx] = updated;
      else next.unshift(updated);
      return next.sort((a, b) => b.id - a.id);
    });
    setSelectedAssessmentId(updated.id);
    hydrateFormFromAssessment(updated);
  }

  async function handleCreateDraft() {
    if (selectedFlightTestId === '') {
      toast.warning('Select a flight test first.');
      return;
    }
    setSaving(true);
    try {
      const created = await ApiService.createFratAssessment({
        flight_test_id: Number(selectedFlightTestId),
        dataset_version_id: form.datasetVersionId === '' ? null : Number(form.datasetVersionId),
        assessment_name: form.assessmentName.trim() || null,
        analysis_job_ids: Array.from(form.selectedAnalysisJobIds),
        inputs: buildInputsPayload(),
      });
      updateAssessmentList(created);
      toast.success(`Created FRAT assessment #${created.id}.`);
    } catch (err) {
      toast.error('Could not create FRAT draft', err instanceof Error ? err.message : undefined);
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveDraft() {
    if (!selectedAssessmentId) {
      toast.warning('Select or create an assessment first.');
      return;
    }
    setSaving(true);
    try {
      const updated = await ApiService.updateFratAssessment(Number(selectedAssessmentId), {
        dataset_version_id: form.datasetVersionId === '' ? null : Number(form.datasetVersionId),
        assessment_name: form.assessmentName.trim() || null,
        analysis_job_ids: Array.from(form.selectedAnalysisJobIds),
        inputs: buildInputsPayload(),
      });
      updateAssessmentList(updated);
      toast.success(`Saved FRAT assessment #${updated.id}.`);
    } catch (err) {
      toast.error('Could not save FRAT draft', err instanceof Error ? err.message : undefined);
    } finally {
      setSaving(false);
    }
  }

  async function handleScore() {
    if (!selectedAssessmentId) {
      toast.warning('Select or create an assessment first.');
      return;
    }
    setScoring(true);
    try {
      const scored = await ApiService.scoreFratAssessment(Number(selectedAssessmentId));
      updateAssessmentList(scored);
      toast.success(
        `Assessment scored: ${String(scored.score_snapshot?.risk_band ?? 'unknown').toUpperCase()}`
      );
    } catch (err) {
      toast.error('Could not score assessment', err instanceof Error ? err.message : undefined);
    } finally {
      setScoring(false);
    }
  }

  async function runTransition(action: 'approve' | 'reject' | 'finalize') {
    if (!selectedAssessmentId) {
      toast.warning('Select an assessment first.');
      return;
    }
    setTransitioning(true);
    try {
      let updated: FratAssessment;
      const notes = form.transitionNotes.trim() || undefined;
      if (action === 'approve') {
        updated = await ApiService.approveFratAssessment(Number(selectedAssessmentId), notes);
      } else if (action === 'reject') {
        updated = await ApiService.rejectFratAssessment(Number(selectedAssessmentId), notes);
      } else {
        updated = await ApiService.finalizeFratAssessment(Number(selectedAssessmentId), notes);
      }
      updateAssessmentList(updated);
      toast.success(`Assessment ${action}d successfully.`);
    } catch (err) {
      toast.error(
        `Could not ${action} assessment`,
        err instanceof Error ? err.message : undefined
      );
    } finally {
      setTransitioning(false);
    }
  }

  async function handleExport() {
    if (!selectedAssessmentId) {
      toast.warning('Select an assessment first.');
      return;
    }
    if (!canExport) {
      toast.warning(exportBlockedMessage);
      return;
    }
    setExporting(true);
    try {
      const blob = await ApiService.exportFratAssessmentPDF(Number(selectedAssessmentId));
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `FTIAS_FRAT_${selectedAssessmentId}_${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success('FRAT PDF downloaded.');
    } catch (err) {
      toast.error('FRAT export failed', err instanceof Error ? err.message : undefined);
    } finally {
      setExporting(false);
    }
  }

  async function handleLookupAssessmentById() {
    const id = Number(assessmentIdLookup);
    if (!assessmentIdLookup.trim() || Number.isNaN(id) || id <= 0) {
      toast.warning('Enter a valid assessment ID.');
      return;
    }
    setLoadingContext(true);
    try {
      const item = await ApiService.getFratAssessment(id);
      if (selectedFlightTestId !== '' && item.flight_test_id !== Number(selectedFlightTestId)) {
        toast.warning(
          `Assessment #${id} belongs to flight test #${item.flight_test_id}. Switch flight test to open it.`
        );
        return;
      }
      setSelectedAssessmentId(item.id);
      updateAssessmentList(item);
      toast.success(`Loaded FRAT assessment #${id}.`);
    } catch (err) {
      toast.error('Could not load FRAT assessment', err instanceof Error ? err.message : undefined);
    } finally {
      setLoadingContext(false);
    }
  }

  function toggleAnalysisJob(id: number) {
    setForm((prev) => {
      const next = new Set(prev.selectedAnalysisJobIds);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return { ...prev, selectedAnalysisJobIds: next };
    });
  }

  const scoreSnapshot = selectedAssessment?.score_snapshot;
  const explanation = selectedAssessment?.decision_explanation;
  const scoreComposition = explanation?.score_composition;
  const linkedAnalysisExplanation = explanation?.linked_analysis;
  const decisionExplanation = explanation?.decision;
  const dominantRiskDrivers = explanation?.dominant_risk_drivers ?? [];
  const hardStops = selectedAssessment?.hard_stop_snapshot ?? [];
  const scoreStatusText =
    scoreSnapshot && scoreSnapshot.total_score != null
      ? `${scoreSnapshot.total_score} points`
      : 'Not scored yet';
  const hasScore = scoreSnapshot?.total_score != null;
  const canExport = !!selectedAssessmentId && hasScore;
  const exportBlockedMessage =
    selectedAssessmentId && !hasScore
      ? 'Export is unavailable until this draft has been scored.'
      : 'Select a scored assessment to export a FRAT report.';
  const localCategoryBaseScore = CATEGORY_FIELDS.reduce(
    (total, field) => total + form.categories[field.key].score,
    0
  );
  const activeHardStopLabels = (
    Object.entries(form.criticalFlags) as Array<[keyof FratFormState['criticalFlags'], boolean]>
  )
    .filter(([, active]) => active)
    .map(([key]) => HARD_STOP_LABELS[key]);
  const scoredHardStopLabels = hardStops
    .map((item) => item.message || item.code)
    .filter((item): item is string => Boolean(item));
  const hasActiveHardStops =
    activeHardStopLabels.length > 0 ||
    scoreSnapshot?.hard_stop_triggered ||
    hardStops.length > 0;
  const linkedAnalysisCount = form.selectedAnalysisJobIds.size;
  const categoryBaseScore = scoreComposition?.base_score ?? scoreSnapshot?.base_score;
  const manualAdjustmentScore =
    scoreComposition?.manual_adjustment ?? scoreSnapshot?.manual_adjustment ?? form.manualAdjustment;
  const analysisIndicatorScore =
    scoreComposition?.analysis_indicator_score ?? scoreSnapshot?.analysis_indicator_score ?? 0;
  const finalTotalScore = scoreComposition?.final_total_score ?? scoreSnapshot?.total_score;
  const riskBand = scoreSnapshot?.risk_band ?? scoreComposition?.risk_band ?? undefined;
  const riskIsModerateOrHigher = ['moderate', 'high', 'unacceptable'].includes(riskBand ?? '');
  const missingManualRationale = form.manualAdjustment !== 0 && !form.overrideNote.trim();
  const missingRiskBasisNotes = hasScore && riskIsModerateOrHigher && linkedAnalysisCount === 0 && !form.reviewerNotes.trim();
  const workflowMessage = workflowStatusMessage({
    status: selectedAssessmentStatus,
    hasScore,
    hasHardStop: !!hasActiveHardStops,
    canExport,
  });

  const canApprove =
    selectedAssessmentStatus === 'scored' || selectedAssessmentStatus === 'needs_review';
  const canFinalize = selectedAssessmentStatus === 'approved';

  return (
    <Sidebar>
      <div className="mx-auto w-full max-w-[1400px] p-4 sm:p-6 lg:p-8 space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">FRAT / Mission Risk</h1>
            <p className="text-gray-500 mt-1">
              Deterministic mission risk scoring with hard-stops, approval workflow, and immutable export.
            </p>
            <a
              href="/help#frat"
              className="mt-2 inline-block text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline"
            >
              FRAT checklist and scoring guide
            </a>
          </div>
          <Badge className="border border-blue-200 bg-blue-50 text-blue-700">P2.5</Badge>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Assessment Scope</CardTitle>
            <CardDescription>Select a flight test and manage FRAT assessments.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Flight Test</label>
                <select
                  value={selectedFlightTestId}
                  onChange={(e) =>
                    setSelectedFlightTestId(e.target.value === '' ? '' : Number(e.target.value))
                  }
                  disabled={loadingTests}
                  className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm"
                >
                  <option value="">
                    {loadingTests ? 'Loading flight tests…' : '— Select flight test —'}
                  </option>
                  {flightTests.map((item) => (
                    <option key={item.id} value={item.id}>
                      #{item.id} · {item.test_name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Saved Assessments</label>
                <select
                  value={selectedAssessmentId}
                  onChange={(e) => {
                    const value = e.target.value === '' ? '' : Number(e.target.value);
                    setSelectedAssessmentId(value);
                    if (value === '') return;
                    const item = assessments.find((assessment) => assessment.id === value);
                    if (item) hydrateFormFromAssessment(item);
                  }}
                  disabled={selectedFlightTestId === '' || loadingContext}
                  className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm"
                >
                  <option value="">— Select assessment —</option>
                  {assessments.map((item) => (
                    <option key={item.id} value={item.id}>
                      #{item.id} · {item.assessment_name || 'Untitled'} · {item.status}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Open by ID</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    min={1}
                    value={assessmentIdLookup}
                    onChange={(e) => setAssessmentIdLookup(e.target.value)}
                    className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm"
                    placeholder="Assessment ID"
                  />
                  <Button variant="outline" onClick={handleLookupAssessmentById} disabled={loadingContext}>
                    Open
                  </Button>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 text-sm text-gray-600">
              <ClipboardList className="w-4 h-4 text-blue-600" />
              <span>
                Active scope: <strong>{selectedFlightTestName}</strong>
              </span>
              {selectedAssessment ? (
                <Badge className={`border ${statusClasses(selectedAssessment.status)}`}>
                  {selectedAssessment.status}
                </Badge>
              ) : null}
            </div>
          </CardContent>
        </Card>

        {selectedFlightTestId !== '' && (
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <div className="xl:col-span-2 space-y-6">
              <Card className={hasActiveHardStops ? 'border-rose-200 bg-rose-50/60' : 'border-blue-100 bg-blue-50/40'}>
                <CardContent className="pt-5">
                  <div className="flex gap-3">
                    {hasActiveHardStops ? (
                      <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" />
                    ) : (
                      <ClipboardList className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />
                    )}
                    <div className={hasActiveHardStops ? 'text-rose-900' : 'text-blue-900'}>
                      <p className="text-sm font-semibold">Workflow status</p>
                      <p className="mt-1 text-sm">{workflowMessage}</p>
                      <div className="mt-2 flex flex-wrap gap-2 text-xs">
                        <Badge className={`border ${statusClasses(selectedAssessmentStatus)}`}>
                          {selectedAssessmentStatus}
                        </Badge>
                        <Badge className="border border-gray-200 bg-white text-gray-700">
                          {hasScore ? 'Scored' : 'Scoring needed'}
                        </Badge>
                        <Badge className={hasActiveHardStops ? 'border border-rose-200 bg-rose-100 text-rose-800' : 'border border-emerald-200 bg-emerald-100 text-emerald-800'}>
                          {hasActiveHardStops ? 'Hard-stop active' : 'No hard-stop selected'}
                        </Badge>
                        <Badge className={canExport ? 'border border-emerald-200 bg-emerald-100 text-emerald-800' : 'border border-gray-200 bg-white text-gray-700'}>
                          {canExport ? 'Export available' : 'Export unavailable'}
                        </Badge>
                      </div>
                      {hasActiveHardStops ? (
                        <p className="mt-2 rounded-md border border-rose-200 bg-white/70 px-3 py-2 text-xs">
                          Hard stops override normal score interpretation. Active flags:{' '}
                          <strong>
                            {activeHardStopLabels.concat(scoredHardStopLabels).join(', ') || 'hard-stop triggered'}
                          </strong>
                          . A low numeric score does not cancel a hard-stop.
                        </p>
                      ) : null}
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Assessment Inputs</CardTitle>
                  <CardDescription>
                    Inputs are persisted in backend snapshot form and used for deterministic FRAT scoring.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        Assessment Name
                      </label>
                      <p className="mb-1.5 text-xs text-gray-500">{FIELD_GUIDANCE.assessmentName}</p>
                      <input
                        type="text"
                        value={form.assessmentName}
                        onChange={(e) => setForm((prev) => ({ ...prev, assessmentName: e.target.value }))}
                        disabled={!canEdit}
                        className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm disabled:opacity-60"
                        placeholder="Mission window / profile name"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        Dataset Version
                      </label>
                      <p className="mb-1.5 text-xs text-gray-500">{FIELD_GUIDANCE.datasetVersion}</p>
                      <select
                        value={form.datasetVersionId}
                        onChange={(e) =>
                          setForm((prev) => ({
                            ...prev,
                            datasetVersionId: e.target.value === '' ? '' : Number(e.target.value),
                          }))
                        }
                        disabled={!canEdit}
                        className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm disabled:opacity-60"
                      >
                        <option value="">— none —</option>
                        {datasetVersions.map((version) => (
                          <option key={version.id} value={version.id}>
                            {version.label} · {version.status}
                            {version.is_active ? ' · active' : ''}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        Requested Authority
                      </label>
                      <p className="mb-1.5 text-xs text-gray-500">{FIELD_GUIDANCE.requestedAuthority}</p>
                      <select
                        value={form.requestedDecisionAuthority}
                        onChange={(e) =>
                          setForm((prev) => ({
                            ...prev,
                            requestedDecisionAuthority:
                              e.target.value === 'advisory' ? 'advisory' : 'authoritative',
                          }))
                        }
                        disabled={!canEdit}
                        className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm disabled:opacity-60"
                      >
                        <option value="authoritative">Authoritative decision support</option>
                        <option value="advisory">Advisory mission support</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        Manual Adjustment (-10 to 10)
                      </label>
                      <p className="mb-1.5 text-xs text-gray-500">{FIELD_GUIDANCE.manualAdjustment}</p>
                      <input
                        type="number"
                        min={-10}
                        max={10}
                        step={1}
                        value={form.manualAdjustment}
                        onChange={(e) =>
                          setForm((prev) => ({
                            ...prev,
                            manualAdjustment: normalizeNumber(e.target.value, -10, 10),
                          }))
                        }
                        disabled={!canEdit}
                        className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm disabled:opacity-60"
                      />
                    </div>
                  </div>

                  <div>
                    <p className="text-sm font-medium text-gray-700 mb-2">Linked Analysis Jobs</p>
                    <p className="mb-2 text-xs text-gray-500">{FIELD_GUIDANCE.linkedAnalysis}</p>
                    {analysisJobs.length === 0 ? (
                      <div className="rounded-lg border border-dashed border-gray-200 px-3 py-2 text-xs text-gray-500">
                        No analysis jobs available yet for this flight test.
                      </div>
                    ) : (
                      <div className="max-h-40 overflow-auto rounded-lg border border-gray-200 divide-y divide-gray-100">
                        {analysisJobs.map((job) => {
                          const checked = form.selectedAnalysisJobIds.has(job.id);
                          return (
                            <label
                              key={job.id}
                              className="flex items-start gap-2 px-3 py-2 text-xs cursor-pointer hover:bg-gray-50"
                            >
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => toggleAnalysisJob(job.id)}
                                disabled={!canEdit}
                                className="mt-0.5"
                              />
                              <span className="flex-1 text-gray-700">
                                #{job.id} · {job.analysis_mode}
                                {job.dataset_version_id ? ` · dataset ${job.dataset_version_id}` : ''}
                                {job.model_name ? ` · ${job.model_name}` : ''}
                                <span className="text-gray-500"> · {formatDateTime(job.created_at)}</span>
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  <div>
                    <div className="mb-2 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-700">
                          Category Scores (0-20 per category)
                        </p>
                        <p className="text-xs text-gray-500">
                          Input preview category base: <strong>{localCategoryBaseScore}</strong>. Backend score is authoritative after scoring.
                        </p>
                      </div>
                      <a href="/help#frat" className="text-xs font-medium text-blue-600 hover:text-blue-700 hover:underline">
                        FRAT scoring guide
                      </a>
                    </div>
                    <details className="mb-3 rounded-lg border border-blue-100 bg-blue-50/70 px-3 py-2 text-xs text-blue-900">
                      <summary className="cursor-pointer font-semibold">0-20 category scoring interpretation</summary>
                      <div className="mt-2 grid grid-cols-1 gap-1.5 md:grid-cols-5">
                        {SCORE_GUIDE.map(([range, level, meaning]) => (
                          <div key={range} className="rounded-md border border-blue-100 bg-white px-2 py-2">
                            <p className="font-semibold">{range}: {level}</p>
                            <p className="mt-1 text-blue-800">{meaning}</p>
                          </div>
                        ))}
                      </div>
                    </details>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {CATEGORY_FIELDS.map((field) => (
                        <div key={field.key} className="rounded-lg border border-gray-200 p-3 space-y-2">
                          <label className="block text-xs font-semibold uppercase tracking-wide text-gray-500">
                            {field.label}
                          </label>
                          <p className="text-xs text-gray-500">{CATEGORY_GUIDANCE[field.key]}</p>
                          <input
                            type="number"
                            min={0}
                            max={20}
                            step={1}
                            value={form.categories[field.key].score}
                            onChange={(e) =>
                              setForm((prev) => ({
                                ...prev,
                                categories: {
                                  ...prev.categories,
                                  [field.key]: {
                                    ...prev.categories[field.key],
                                    score: normalizeNumber(e.target.value, 0, 20),
                                  },
                                },
                              }))
                            }
                            disabled={!canEdit}
                            className="w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-sm disabled:opacity-60"
                          />
                          <textarea
                            value={form.categories[field.key].notes}
                            onChange={(e) =>
                              setForm((prev) => ({
                                ...prev,
                                categories: {
                                  ...prev.categories,
                                  [field.key]: {
                                    ...prev.categories[field.key],
                                    notes: e.target.value,
                                  },
                                },
                              }))
                            }
                            disabled={!canEdit}
                            rows={2}
                            className="w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-xs disabled:opacity-60"
                            placeholder="Category notes"
                          />
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 space-y-2">
                    <p className="text-sm font-semibold text-amber-900">Critical Hard-Stop Flags</p>
                    <p className="text-xs text-amber-900">
                      Select only when the condition should force no-go/review behavior regardless of the numeric score.
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs text-amber-900">
                      {[
                        ['critical_system_unavailable', 'Critical system unavailable'],
                        ['mandatory_data_missing', 'Mandatory data missing'],
                        ['crew_unfit', 'Crew unfit'],
                      ].map(([key, label]) => (
                        <label key={key} className="inline-flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={
                              form.criticalFlags[key as keyof FratFormState['criticalFlags']]
                            }
                            onChange={(e) =>
                              setForm((prev) => ({
                                ...prev,
                                criticalFlags: {
                                  ...prev.criticalFlags,
                                  [key]: e.target.checked,
                                },
                              }))
                            }
                            disabled={!canEdit}
                          />
                          <span>
                            <span className="font-medium">{label}</span>
                            <span className="mt-0.5 block text-amber-800">
                              {HARD_STOP_GUIDANCE[key as keyof FratFormState['criticalFlags']]}
                            </span>
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>

                  {hasActiveHardStops ? (
                    <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-900">
                      <AlertTriangle className="mr-1.5 inline h-4 w-4" />
                      Hard-stop selected. Resolve the condition or document rejection/no-go rationale; normal score totals do not override this state.
                    </div>
                  ) : null}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        Reviewer Notes
                      </label>
                      <p className="mb-1.5 text-xs text-gray-500">{FIELD_GUIDANCE.reviewNotes}</p>
                      <textarea
                        value={form.reviewerNotes}
                        onChange={(e) => setForm((prev) => ({ ...prev, reviewerNotes: e.target.value }))}
                        rows={4}
                        disabled={!canEdit}
                        className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm disabled:opacity-60"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1.5">
                        Override / Rationale Notes
                      </label>
                      <p className="mb-1.5 text-xs text-gray-500">{FIELD_GUIDANCE.overrideNote}</p>
                      <textarea
                        value={form.overrideNote}
                        onChange={(e) => setForm((prev) => ({ ...prev, overrideNote: e.target.value }))}
                        rows={4}
                        disabled={!canEdit}
                        className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm disabled:opacity-60"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">
                      Transition Notes (approve/reject/finalize)
                    </label>
                    <p className="mb-1.5 text-xs text-gray-500">{FIELD_GUIDANCE.transitionNotes}</p>
                    <textarea
                      value={form.transitionNotes}
                      onChange={(e) => setForm((prev) => ({ ...prev, transitionNotes: e.target.value }))}
                      rows={3}
                      className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm"
                    />
                  </div>

                  {missingManualRationale ? (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                      Manual adjustment is non-zero. Add override/rationale notes so reviewers can trace why the final score changed.
                    </div>
                  ) : null}
                  {missingRiskBasisNotes ? (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                      This scored assessment is moderate or higher with no linked analysis. Add review notes explaining the risk basis.
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            </div>

            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Workflow Actions</CardTitle>
                  <CardDescription>
                    Draft → Score → Review/Approve → Finalize (immutable)
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2">
                  <Button
                    className="w-full"
                    onClick={handleCreateDraft}
                    disabled={saving}
                  >
                    {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                    Create Draft
                  </Button>
                  <Button
                    className="w-full"
                    variant="outline"
                    onClick={handleSaveDraft}
                    disabled={saving || !selectedAssessmentId || !canEdit}
                  >
                    Save Draft
                  </Button>
                  <Button
                    className="w-full"
                    variant="outline"
                    onClick={handleScore}
                    disabled={scoring || !selectedAssessmentId || !canEdit}
                  >
                    {scoring ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                    Score Assessment
                  </Button>
                  <Button
                    className="w-full"
                    variant="outline"
                    onClick={() => runTransition('approve')}
                    disabled={transitioning || !selectedAssessmentId || !canApprove}
                  >
                    Approve
                  </Button>
                  <Button
                    className="w-full"
                    variant="outline"
                    onClick={() => runTransition('reject')}
                    disabled={transitioning || !selectedAssessmentId || selectedAssessmentStatus === 'finalized'}
                  >
                    Reject
                  </Button>
                  <Button
                    className="w-full"
                    variant="outline"
                    onClick={() => runTransition('finalize')}
                    disabled={transitioning || !selectedAssessmentId || !canFinalize}
                  >
                    Finalize
                  </Button>
                  <Button
                    className="w-full"
                    variant="outline"
                    onClick={handleExport}
                    disabled={exporting || !canExport}
                    title={!canExport ? exportBlockedMessage : 'Export FRAT PDF report'}
                  >
                    {exporting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <FileDown className="w-4 h-4 mr-2" />}
                    Export FRAT PDF
                  </Button>
                  {!canExport ? (
                    <p className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600">
                      {exportBlockedMessage}
                    </p>
                  ) : null}
                  <a href="/help#reports" className="text-xs font-medium text-blue-600 hover:text-blue-700 hover:underline">
                    Report and PDF generation guidance
                  </a>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Scoring Snapshot</CardTitle>
                  <CardDescription>
                    Authoritative values come from the backend score snapshot after scoring.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-700">
                    <p className="font-semibold">Final Score = Category Base Score + Manual Adjustment + Analysis Indicator Score</p>
                    <p className="mt-1">
                      Category input preview: {localCategoryBaseScore}. Backend score composition appears after scoring.
                    </p>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-500">Status</span>
                    <Badge className={`border ${statusClasses(selectedAssessmentStatus)}`}>
                      {selectedAssessmentStatus}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-500">Score</span>
                    <span className="text-sm font-semibold text-gray-900">{scoreStatusText}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-500">Risk Band</span>
                    <span className={`text-sm font-semibold ${riskBandClasses(scoreSnapshot?.risk_band)}`}>
                      {(scoreSnapshot?.risk_band ?? '—').toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-500">Recommendation</span>
                    <span className="text-sm font-semibold text-gray-900">
                      {(scoreSnapshot?.recommendation ?? '—').toUpperCase()}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 rounded-md border border-gray-200 bg-gray-50 px-3 py-2">
                    {scoreSnapshot?.hard_stop_triggered ? (
                      <ShieldAlert className="w-4 h-4 text-rose-600" />
                    ) : (
                      <ShieldCheck className="w-4 h-4 text-emerald-600" />
                    )}
                    <span className="text-xs text-gray-700">
                      {scoreSnapshot?.hard_stop_triggered
                        ? 'Hard-stop triggered: no-go override active.'
                        : 'No hard-stop triggered.'}
                    </span>
                  </div>
                  {hasScore ? (
                    <div className="grid grid-cols-2 gap-2 text-center md:grid-cols-4">
                      <div className="rounded-md border border-gray-200 bg-white px-2 py-2">
                        <p className="text-[11px] text-gray-500">Category Base</p>
                        <p className="text-sm font-semibold text-gray-900">
                          {categoryBaseScore ?? 0}
                        </p>
                      </div>
                      <div className="rounded-md border border-gray-200 bg-white px-2 py-2">
                        <p className="text-[11px] text-gray-500">Manual</p>
                        <p className="text-sm font-semibold text-gray-900">
                          {manualAdjustmentScore ?? 0}
                        </p>
                      </div>
                      <div className="rounded-md border border-gray-200 bg-white px-2 py-2">
                        <p className="text-[11px] text-gray-500">Analysis Indicator</p>
                        <p className="text-sm font-semibold text-gray-900">
                          {analysisIndicatorScore}
                        </p>
                      </div>
                      <div className="rounded-md border border-gray-200 bg-white px-2 py-2">
                        <p className="text-[11px] text-gray-500">Total</p>
                        <p className="text-sm font-semibold text-gray-900">
                          {finalTotalScore ?? '—'}
                        </p>
                      </div>
                    </div>
                  ) : null}
                  {linkedAnalysisCount === 0 ? (
                    <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-900">
                      No linked analysis job is attached. Technical analysis evidence is not included in this FRAT score.
                    </div>
                  ) : (
                    <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-900">
                      Linked analysis controls contributed <strong>{analysisIndicatorScore}</strong> point{analysisIndicatorScore === 1 ? '' : 's'} to the final score.
                    </div>
                  )}
                </CardContent>
              </Card>

              {explanation ? (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Decision Explanation</CardTitle>
                    <CardDescription>
                      Traceable explanation generated from the scored FRAT snapshot.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {linkedAnalysisExplanation?.warning ? (
                      <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                        <AlertTriangle className="w-4 h-4 inline mr-1.5" />
                        {linkedAnalysisExplanation.warning}
                      </div>
                    ) : null}
                    {!linkedAnalysisExplanation?.available && linkedAnalysisExplanation?.no_linked_analysis_statement ? (
                      <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-900">
                        {linkedAnalysisExplanation.no_linked_analysis_statement}
                      </div>
                    ) : null}

                    {decisionExplanation?.why_not_acceptable?.length ? (
                      <div>
                        <p className="text-sm font-medium text-gray-700 mb-1">Decision basis</p>
                        <ul className="space-y-1 text-xs text-gray-700">
                          {decisionExplanation.why_not_acceptable.map((item, idx) => (
                            <li key={`${item}-${idx}`} className="rounded-md bg-gray-50 px-2 py-1">
                              {item}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : (
                      <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
                        Assessment is acceptable under the current scored decision state.
                      </div>
                    )}

                    {dominantRiskDrivers.length ? (
                      <div>
                        <p className="text-sm font-medium text-gray-700 mb-1">Dominant risk drivers</p>
                        <div className="space-y-1">
                          {dominantRiskDrivers.map((item, idx) => (
                            <div key={`${item.type ?? 'driver'}-${idx}`} className="rounded-md border border-gray-200 px-2 py-1.5 text-xs text-gray-700">
                              <span className="font-semibold">{item.label ?? item.type}</span>
                              {item.score != null ? ` · ${item.score} pts` : ''}
                              {item.reason ? <span className="block text-gray-500">{item.reason}</span> : null}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    {decisionExplanation?.recommended_next_actions?.length ? (
                      <div>
                        <p className="text-sm font-medium text-gray-700 mb-1">Recommended next actions</p>
                        <ul className="space-y-1 text-xs text-gray-700">
                          {decisionExplanation.recommended_next_actions.map((item, idx) => (
                            <li key={`${item}-${idx}`} className="rounded-md bg-gray-50 px-2 py-1">
                              {item}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </CardContent>
                </Card>
              ) : null}

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Hard-Stop Details</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {hardStops.length === 0 ? (
                    <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
                      <CheckCircle2 className="w-4 h-4 inline mr-1.5" />
                      No hard-stop conditions in current snapshot.
                    </div>
                  ) : (
                    hardStops.map((item, idx) => (
                      <div
                        key={`${item.code ?? 'hard-stop'}-${idx}`}
                        className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-900"
                      >
                        <AlertTriangle className="w-4 h-4 inline mr-1.5" />
                        <strong>{item.code ?? 'hard-stop'}</strong>
                        {item.message ? `: ${item.message}` : ''}
                      </div>
                    ))
                  )}
                  <p className="text-xs text-gray-500">
                    Scored FRAT assessments can be exported for Go, Review, Rejected, and No-Go cases.
                  </p>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </div>
      <ToastContainer toasts={toast.toasts} onDismiss={toast.dismiss} />
    </Sidebar>
  );
}
