import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  ClipboardCheck,
  Database,
  FileDown,
  HelpCircle,
  ShieldAlert,
  Sparkles,
  Upload,
} from 'lucide-react';
import Sidebar from '../components/Sidebar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';

const MANUAL_URL = '/manual/FTIAS-MANUAL-V00.pdf';

const helpTopics = [
  {
    id: 'upload',
    title: 'Upload Data',
    icon: Upload,
    description: 'CSV preparation, ingestion checklist, upload history, failed upload cleanup.',
  },
  {
    id: 'dataset-versioning',
    title: 'Dataset Versioning',
    icon: Database,
    description: 'Immutable dataset versions, active dataset selection, and provenance rules.',
  },
  {
    id: 'parameters',
    title: 'Parameters and Charts',
    icon: BarChart3,
    description: 'Parameter search, chart overlays, comparison, saved sets, and chart export.',
  },
  {
    id: 'ai-analysis',
    title: 'AI Analysis',
    icon: Sparkles,
    description: 'Mode selection, prompt-to-mode guard, controls, limitations, saved artifacts, and performance/climb/air-data interpretation.',
  },
  {
    id: 'air-data',
    title: 'Performance / Climb / Air Data',
    icon: BarChart3,
    description: 'Altitude, climb/descent, CAS/TAS/Mach, ISA, pressure-altitude, density-altitude, and air-data consistency support.',
  },
  {
    id: 'reports',
    title: 'Reports',
    icon: FileDown,
    description: 'PDF export readiness, saved analysis provenance, controls, warnings, and charts.',
  },
  {
    id: 'frat',
    title: 'FRAT',
    icon: ShieldAlert,
    description: 'Mission-risk scoring, hard stops, review decisions, no-go explanations, and export.',
  },
  {
    id: 'troubleshooting',
    title: 'Troubleshooting',
    icon: AlertTriangle,
    description: 'Upload failures, missing data, report availability, and interpretation boundaries.',
  },
];

export default function Help() {
  return (
    <Sidebar>
      <div className="mx-auto w-full max-w-[1200px] p-4 sm:p-6 lg:p-8 space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
              <HelpCircle className="h-3.5 w-3.5" />
              Manual / Help
            </div>
            <h1 className="text-3xl font-bold text-gray-900">FTIAS Manual / Help</h1>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-gray-600">
              Use this page as the in-app starting point for the FTIAS Manual V-00 and quick workflow
              guidance. The manual covers ingestion, dataset versioning, parameter exploration,
              AI-assisted analysis, reports, FRAT mission risk, and troubleshooting.
            </p>
          </div>
          <a
            href={MANUAL_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
          >
            <BookOpen className="h-4 w-4" />
            Open Manual V-00
          </a>
        </div>

        <Card className="border-amber-200 bg-amber-50/70">
          <CardContent className="pt-5">
            <div className="flex gap-3">
              <ClipboardCheck className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
              <div className="space-y-1 text-sm text-amber-900">
                <p className="font-semibold">Responsible use reminder</p>
                <p>
                  FTIAS is an engineering support system. It does not provide certification approval,
                  flutter clearance, or operational authorization. Qualified personnel remain responsible
                  for review, acceptance, and release decisions.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {helpTopics.map((topic) => {
            const Icon = topic.icon;
            return (
              <Card key={topic.id} id={topic.id} className="scroll-mt-6">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Icon className="h-4 w-4 text-blue-600" />
                    {topic.title}
                  </CardTitle>
                  <CardDescription>{topic.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <a
                    href={MANUAL_URL}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-medium text-blue-600 hover:text-blue-700 hover:underline"
                  >
                    Open Manual V-00 for this workflow
                  </a>
                </CardContent>
              </Card>
            );
          })}
        </div>

        <Card id="air-data-guidance" className="border-blue-100 bg-blue-50/50">
          <CardHeader>
            <CardTitle className="text-base">Air-Data Interpretation Boundaries</CardTitle>
            <CardDescription>
              Use the Performance / Climb / Air Data mode as bounded engineering support.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-blue-900">
            <p>
              Supported prompts may reference altitude, climb/descent, airspeed, Mach, ISA,
              pressure-altitude, density-altitude, and air-data consistency when the relevant
              channels are present.
            </p>
            <p>
              CAS/TAS/Mach consistency depends on sensor quality, units, and synchronized timestamps.
              Missing pressure, temperature, or calibrated-speed channels can reduce applicability.
            </p>
            <p>
              ISA and density-altitude outputs are engineering support only unless certification
              correction models are explicitly applied. FTIAS does not provide certification approval.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Manual File</CardTitle>
            <CardDescription>Served from the frontend static assets for stable in-app access.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-gray-600">
            <p>
              In-app URL:{' '}
              <a href={MANUAL_URL} target="_blank" rel="noreferrer" className="font-medium text-blue-600 hover:underline">
                {MANUAL_URL}
              </a>
            </p>
            <p>Repository source file: <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs">FTIAS-MANUAL-V00.pdf</code></p>
          </CardContent>
        </Card>
      </div>
    </Sidebar>
  );
}
