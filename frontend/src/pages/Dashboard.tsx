import { useEffect, useState, useMemo } from 'react';
import { Search, Plus, Plane, Calendar, Clock, Filter, Download, X } from 'lucide-react';
import { useLocation } from 'wouter';
import Sidebar from '../components/Sidebar';
import FlightTestModal from '../components/FlightTestModal';
import { ToastContainer, useToast } from '../components/ui/toast';
import { ApiService, FlightTest } from '../services/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { cn } from '@/lib/utils';

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function formatDuration(seconds: number | null): string | null {
  if (seconds === null) return null;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m`;
  return `${seconds}s`;
}

function exportToCSV(tests: FlightTest[]) {
  const headers = ['ID', 'Test Name', 'Aircraft Type', 'Test Date', 'Duration (s)', 'Description', 'Created At'];
  const rows = tests.map((t) => [
    t.id,
    `"${t.test_name.replace(/"/g, '""')}"`,
    `"${t.aircraft_type.replace(/"/g, '""')}"`,
    t.test_date,
    t.duration_seconds ?? '',
    `"${(t.description ?? '').replace(/"/g, '""')}"`,
    t.created_at,
  ]);

  const csv = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `ftias-flight-tests-${new Date().toISOString().split('T')[0]}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export default function Dashboard() {
  const [, setLocation] = useLocation();
  const toast = useToast();

  const [flightTests, setFlightTests] = useState<FlightTest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Filters
  const [showFilters, setShowFilters] = useState(false);
  const [aircraftFilter, setAircraftFilter] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  useEffect(() => {
    loadFlightTests();
  }, []);

  const loadFlightTests = async () => {
    try {
      setIsLoading(true);
      setError('');
      const tests = await ApiService.getFlightTests();
      setFlightTests(tests);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load flight tests');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateSuccess = (newTest: FlightTest) => {
    setFlightTests((prev) => [newTest, ...prev]);
    toast.success('Flight test created', `"${newTest.test_name}" has been added successfully.`);
  };

  // Unique aircraft types for filter dropdown
  const aircraftTypes = useMemo(
    () => Array.from(new Set(flightTests.map((t) => t.aircraft_type))).sort(),
    [flightTests]
  );

  const activeFilterCount = [aircraftFilter, dateFrom, dateTo].filter(Boolean).length;

  const filteredTests = useMemo(() => {
    return flightTests.filter((test) => {
      const matchesSearch =
        test.test_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        test.aircraft_type.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesAircraft = !aircraftFilter || test.aircraft_type === aircraftFilter;

      const testDate = test.test_date.split('T')[0];
      const matchesDateFrom = !dateFrom || testDate >= dateFrom;
      const matchesDateTo = !dateTo || testDate <= dateTo;

      return matchesSearch && matchesAircraft && matchesDateFrom && matchesDateTo;
    });
  }, [flightTests, searchQuery, aircraftFilter, dateFrom, dateTo]);

  const clearFilters = () => {
    setAircraftFilter('');
    setDateFrom('');
    setDateTo('');
  };

  return (
    <Sidebar>
      <div className="p-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-1">Flight Tests</h1>
          <p className="text-gray-500">Manage and analyze your flight test data</p>
        </div>

        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
            <Input
              type="text"
              placeholder="Search by name or aircraft type…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Filter toggle */}
          <Button
            variant="outline"
            onClick={() => setShowFilters((v) => !v)}
            className={cn('gap-2', activeFilterCount > 0 && 'border-blue-400 text-blue-600 bg-blue-50')}
          >
            <Filter className="w-4 h-4" />
            Filters
            {activeFilterCount > 0 && (
              <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-600 text-white text-xs">
                {activeFilterCount}
              </span>
            )}
          </Button>

          {/* Export */}
          <Button
            variant="outline"
            onClick={() => {
              exportToCSV(filteredTests);
              toast.success('Exported', `${filteredTests.length} records saved to CSV.`);
            }}
            disabled={filteredTests.length === 0}
            className="gap-2"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </Button>

          {/* New flight test */}
          <Button onClick={() => setShowCreateModal(true)} className="gap-2 ml-auto">
            <Plus className="w-4 h-4" />
            New Flight Test
          </Button>
        </div>

        {/* Filter panel */}
        {showFilters && (
          <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 mb-4 flex flex-wrap gap-4 items-end">
            {/* Aircraft type */}
            <div className="flex-1 min-w-[160px]">
              <label className="block text-xs font-medium text-gray-600 mb-1">Aircraft Type</label>
              <select
                value={aircraftFilter}
                onChange={(e) => setAircraftFilter(e.target.value)}
                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900
                           focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All aircraft</option>
                {aircraftTypes.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>

            {/* Date from */}
            <div className="flex-1 min-w-[140px]">
              <label className="block text-xs font-medium text-gray-600 mb-1">Date From</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900
                           focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Date to */}
            <div className="flex-1 min-w-[140px]">
              <label className="block text-xs font-medium text-gray-600 mb-1">Date To</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900
                           focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Clear */}
            {activeFilterCount > 0 && (
              <Button variant="outline" size="sm" onClick={clearFilters} className="gap-1.5 self-end">
                <X className="w-3.5 h-3.5" />
                Clear filters
              </Button>
            )}
          </div>
        )}

        {/* Stats bar */}
        {!isLoading && !error && flightTests.length > 0 && (
          <p className="text-sm text-gray-500 mb-5">
            {filteredTests.length === flightTests.length
              ? `${flightTests.length} test${flightTests.length !== 1 ? 's' : ''} total`
              : `${filteredTests.length} of ${flightTests.length} tests`}
          </p>
        )}

        {/* Loading */}
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
            <p className="text-gray-500 text-sm">Loading flight tests…</p>
          </div>
        )}

        {/* Error */}
        {error && !isLoading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="text-red-500 text-sm bg-red-50 border border-red-200 rounded-lg px-4 py-3">
              {error}
            </div>
            <Button onClick={loadFlightTests} variant="outline" size="sm">Try Again</Button>
          </div>
        )}

        {/* Grid */}
        {!isLoading && !error && filteredTests.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredTests.map((test) => {
              const duration = formatDuration(test.duration_seconds);
              return (
                <Card
                  key={test.id}
                  className="hover:shadow-md transition-all duration-200 cursor-pointer hover:-translate-y-0.5 border-gray-200"
                  onClick={() => setLocation(`/flight-tests/${test.id}`)}
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between mb-3">
                      <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                        <Plane className="w-5 h-5 text-blue-600" />
                      </div>
                      <Badge variant="secondary" className="text-xs">#{test.id}</Badge>
                    </div>
                    <CardTitle className="text-base leading-snug">{test.test_name}</CardTitle>
                    <CardDescription className="flex items-center gap-1 text-xs">
                      <Calendar className="w-3.5 h-3.5" />
                      {formatDate(test.test_date)}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <div className="space-y-2 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-gray-500">Aircraft</span>
                        <span className="font-medium text-gray-800">{test.aircraft_type}</span>
                      </div>
                      {duration && (
                        <div className="flex items-center justify-between">
                          <span className="text-gray-500 flex items-center gap-1">
                            <Clock className="w-3.5 h-3.5" />Duration
                          </span>
                          <span className="font-medium text-gray-800">{duration}</span>
                        </div>
                      )}
                      {test.description && (
                        <p className="text-gray-500 text-xs line-clamp-2 pt-1 border-t border-gray-100 mt-2">
                          {test.description}
                        </p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && filteredTests.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center">
              <Plane className="w-10 h-10 text-gray-400" />
            </div>
            <div className="text-center">
              <h3 className="text-lg font-semibold text-gray-900 mb-1">
                {searchQuery || activeFilterCount > 0 ? 'No results found' : 'No flight tests yet'}
              </h3>
              <p className="text-gray-500 text-sm">
                {searchQuery || activeFilterCount > 0
                  ? 'Try adjusting your search or filters.'
                  : 'Get started by creating your first flight test record.'}
              </p>
            </div>
            {!searchQuery && activeFilterCount === 0 && (
              <Button onClick={() => setShowCreateModal(true)} className="gap-2 mt-2">
                <Plus className="w-4 h-4" />
                Create Flight Test
              </Button>
            )}
            {activeFilterCount > 0 && (
              <Button variant="outline" onClick={clearFilters} className="gap-2">
                <X className="w-4 h-4" />
                Clear filters
              </Button>
            )}
          </div>
        )}
      </div>

      <FlightTestModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSuccess={handleCreateSuccess}
      />
      <ToastContainer toasts={toast.toasts} onDismiss={toast.dismiss} />
    </Sidebar>
  );
}
