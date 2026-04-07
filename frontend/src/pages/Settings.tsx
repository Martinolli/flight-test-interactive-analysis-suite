import { useState, useEffect } from 'react';
import { Save, RotateCcw, Monitor, Database, Bell, Shield } from 'lucide-react';
import Sidebar from '../components/Sidebar';
import { ToastContainer, useToast } from '../components/ui/toast';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { cn } from '@/lib/utils';

// ─── Persisted settings shape ─────────────────────────────────────────────────

interface AppSettings {
  // Display
  dateFormat: 'MM/DD/YYYY' | 'DD/MM/YYYY' | 'YYYY-MM-DD';
  timeFormat: '12h' | '24h';
  defaultChartHeight: 240 | 320 | 400 | 480;
  showMeanByDefault: boolean;
  // Data
  defaultPageSize: 10 | 25 | 50 | 100;
  autoRefreshInterval: 0 | 30 | 60 | 300; // seconds; 0 = off
  // Notifications
  notifyOnUploadComplete: boolean;
  notifyOnAnalysisComplete: boolean;
}

const DEFAULT_SETTINGS: AppSettings = {
  dateFormat: 'MM/DD/YYYY',
  timeFormat: '12h',
  defaultChartHeight: 320,
  showMeanByDefault: false,
  defaultPageSize: 25,
  autoRefreshInterval: 0,
  notifyOnUploadComplete: true,
  notifyOnAnalysisComplete: true,
};

const STORAGE_KEY = 'ftias_settings';

function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

function saveSettings(s: AppSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
}

// ─── Small helpers ─────────────────────────────────────────────────────────────

function SectionIcon({ icon: Icon, color }: { icon: React.ElementType; color: string }) {
  return (
    <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center shrink-0', color)}>
      <Icon className="w-4.5 h-4.5" />
    </div>
  );
}

function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1',
        checked ? 'bg-blue-600' : 'bg-gray-200',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
    >
      <span
        className={cn(
          'inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform',
          checked ? 'translate-x-6' : 'translate-x-1'
        )}
      />
    </button>
  );
}

function SelectField<T extends string | number>({
  value,
  onChange,
  options,
  disabled,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
  disabled?: boolean;
}) {
  return (
    <select
      value={String(value)}
      onChange={(e) => {
        const raw = e.target.value;
        // Preserve numeric types
        const cast = typeof value === 'number' ? (Number(raw) as T) : (raw as T);
        onChange(cast);
      }}
      disabled={disabled}
      className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-900
                 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {options.map((o) => (
        <option key={String(o.value)} value={String(o.value)}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

// ─── Main component ────────────────────────────────────────────────────────────

export default function Settings() {
  const toast = useToast();
  const [settings, setSettings] = useState<AppSettings>(loadSettings);
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Track unsaved changes
  useEffect(() => {
    const saved = loadSettings();
    setIsDirty(JSON.stringify(settings) !== JSON.stringify(saved));
  }, [settings]);

  const update = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    await new Promise((r) => setTimeout(r, 300)); // simulate async
    saveSettings(settings);
    setIsDirty(false);
    setIsSaving(false);
    toast.success('Settings saved', 'Your preferences have been updated.');
  };

  const handleReset = () => {
    setSettings(DEFAULT_SETTINGS);
    toast.warning('Settings reset', 'All settings restored to defaults.');
  };

  return (
    <Sidebar>
      <div className="p-8 max-w-2xl">
        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-1">Settings</h1>
            <p className="text-gray-500">Configure your FTIAS preferences</p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleReset}
              disabled={isSaving}
              className="gap-1.5"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={!isDirty || isSaving}
              className="gap-1.5"
            >
              <Save className="w-3.5 h-3.5" />
              {isSaving ? 'Saving…' : isDirty ? 'Save Changes' : 'Saved'}
            </Button>
          </div>
        </div>

        <div className="space-y-6">
          {/* ── Display ─────────────────────────────────────────────────────── */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <SectionIcon icon={Monitor} color="bg-blue-50 text-blue-600" />
                <div>
                  <CardTitle>Display</CardTitle>
                  <CardDescription>Date formats and chart defaults</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">Date Format</p>
                  <p className="text-xs text-gray-500">How dates are displayed throughout the app</p>
                </div>
                <SelectField
                  value={settings.dateFormat}
                  onChange={(v) => update('dateFormat', v)}
                  options={[
                    { value: 'MM/DD/YYYY', label: 'MM/DD/YYYY' },
                    { value: 'DD/MM/YYYY', label: 'DD/MM/YYYY' },
                    { value: 'YYYY-MM-DD', label: 'YYYY-MM-DD (ISO)' },
                  ]}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">Time Format</p>
                  <p className="text-xs text-gray-500">12-hour or 24-hour clock</p>
                </div>
                <SelectField
                  value={settings.timeFormat}
                  onChange={(v) => update('timeFormat', v)}
                  options={[
                    { value: '12h', label: '12-hour (AM/PM)' },
                    { value: '24h', label: '24-hour' },
                  ]}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">Default Chart Height</p>
                  <p className="text-xs text-gray-500">Initial height for parameter charts</p>
                </div>
                <SelectField
                  value={settings.defaultChartHeight}
                  onChange={(v) => update('defaultChartHeight', v)}
                  options={[
                    { value: 240, label: '240 px (compact)' },
                    { value: 320, label: '320 px (default)' },
                    { value: 400, label: '400 px (large)' },
                    { value: 480, label: '480 px (extra large)' },
                  ]}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">Show Mean Line by Default</p>
                  <p className="text-xs text-gray-500">Display reference mean on time-series charts</p>
                </div>
                <Toggle
                  checked={settings.showMeanByDefault}
                  onChange={(v) => update('showMeanByDefault', v)}
                />
              </div>
            </CardContent>
          </Card>

          {/* ── Data ────────────────────────────────────────────────────────── */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <SectionIcon icon={Database} color="bg-green-50 text-green-600" />
                <div>
                  <CardTitle>Data</CardTitle>
                  <CardDescription>Pagination and refresh behaviour</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">Default Page Size</p>
                  <p className="text-xs text-gray-500">Number of records shown per page</p>
                </div>
                <SelectField
                  value={settings.defaultPageSize}
                  onChange={(v) => update('defaultPageSize', v)}
                  options={[
                    { value: 10, label: '10 per page' },
                    { value: 25, label: '25 per page' },
                    { value: 50, label: '50 per page' },
                    { value: 100, label: '100 per page' },
                  ]}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">Auto-Refresh Interval</p>
                  <p className="text-xs text-gray-500">Automatically reload flight test list</p>
                </div>
                <SelectField
                  value={settings.autoRefreshInterval}
                  onChange={(v) => update('autoRefreshInterval', v)}
                  options={[
                    { value: 0, label: 'Off' },
                    { value: 30, label: 'Every 30 s' },
                    { value: 60, label: 'Every 1 min' },
                    { value: 300, label: 'Every 5 min' },
                  ]}
                />
              </div>
            </CardContent>
          </Card>

          {/* ── Notifications ───────────────────────────────────────────────── */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <SectionIcon icon={Bell} color="bg-orange-50 text-orange-600" />
                <div>
                  <CardTitle>Notifications</CardTitle>
                  <CardDescription>In-app toast notification preferences</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">Upload Complete</p>
                  <p className="text-xs text-gray-500">Show a notification when a file upload finishes</p>
                </div>
                <Toggle
                  checked={settings.notifyOnUploadComplete}
                  onChange={(v) => update('notifyOnUploadComplete', v)}
                />
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-900">Analysis Complete</p>
                  <p className="text-xs text-gray-500">Show a notification when AI analysis finishes</p>
                </div>
                <Toggle
                  checked={settings.notifyOnAnalysisComplete}
                  onChange={(v) => update('notifyOnAnalysisComplete', v)}
                />
              </div>
            </CardContent>
          </Card>

          {/* ── About ───────────────────────────────────────────────────────── */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <SectionIcon icon={Shield} color="bg-purple-50 text-purple-600" />
                <div>
                  <CardTitle>About FTIAS</CardTitle>
                  <CardDescription>Version and build information</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wide mb-0.5">Application</p>
                  <p className="font-medium text-gray-900">Flight Test Interactive Analysis Suite</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wide mb-0.5">Frontend Version</p>
                  <p className="font-medium text-gray-900">0.4.0</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wide mb-0.5">Stack</p>
                  <p className="font-medium text-gray-900">React 19 · TypeScript · Vite · Tailwind 4</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500 uppercase tracking-wide mb-0.5">Charts</p>
                  <p className="font-medium text-gray-900">Recharts</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <ToastContainer toasts={toast.toasts} onDismiss={toast.dismiss} />
    </Sidebar>
  );
}
