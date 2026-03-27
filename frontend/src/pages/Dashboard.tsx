import { useEffect, useState } from 'react';
import { Search, Plus, Plane, Calendar, Clock } from 'lucide-react';
import { useLocation } from 'wouter';
import Sidebar from '../components/Sidebar';
import FlightTestModal from '../components/FlightTestModal';
import { ToastContainer, useToast } from '../components/ui/toast';
import { ApiService, FlightTest } from '../services/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return null as unknown as string;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m`;
  return `${seconds}s`;
}

export default function Dashboard() {
  const [, setLocation] = useLocation();
  const toast = useToast();

  const [flightTests, setFlightTests] = useState<FlightTest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);

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

  const filteredTests = flightTests.filter(
    (test) =>
      test.test_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      test.aircraft_type.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <Sidebar>
      <div className="p-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-1">Flight Tests</h1>
          <p className="text-gray-500">Manage and analyze your flight test data</p>
        </div>

        {/* Search and Actions */}
        <div className="flex items-center justify-between mb-6 gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
            <Input
              type="text"
              placeholder="Search by name or aircraft type..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Button onClick={() => setShowCreateModal(true)} className="gap-2 shrink-0">
            <Plus className="w-4 h-4" />
            New Flight Test
          </Button>
        </div>

        {/* Stats bar */}
        {!isLoading && !error && flightTests.length > 0 && (
          <div className="flex items-center gap-2 mb-6">
            <span className="text-sm text-gray-500">
              {filteredTests.length === flightTests.length
                ? `${flightTests.length} test${flightTests.length !== 1 ? 's' : ''} total`
                : `${filteredTests.length} of ${flightTests.length} tests`}
            </span>
          </div>
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
            <p className="text-gray-500 text-sm">Loading flight tests...</p>
          </div>
        )}

        {/* Error State */}
        {error && !isLoading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="text-red-500 text-sm bg-red-50 border border-red-200 rounded-lg px-4 py-3">
              {error}
            </div>
            <Button onClick={loadFlightTests} variant="outline" size="sm">
              Try Again
            </Button>
          </div>
        )}

        {/* Flight Tests Grid */}
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
                      <Badge variant="secondary" className="text-xs">
                        #{test.id}
                      </Badge>
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
                            <Clock className="w-3.5 h-3.5" />
                            Duration
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

        {/* Empty State */}
        {!isLoading && !error && filteredTests.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center">
              <Plane className="w-10 h-10 text-gray-400" />
            </div>
            <div className="text-center">
              <h3 className="text-lg font-semibold text-gray-900 mb-1">
                {searchQuery ? 'No results found' : 'No flight tests yet'}
              </h3>
              <p className="text-gray-500 text-sm">
                {searchQuery
                  ? `No tests match "${searchQuery}". Try a different search.`
                  : 'Get started by creating your first flight test record.'}
              </p>
            </div>
            {!searchQuery && (
              <Button onClick={() => setShowCreateModal(true)} className="gap-2 mt-2">
                <Plus className="w-4 h-4" />
                Create Flight Test
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Create Modal */}
      <FlightTestModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSuccess={handleCreateSuccess}
      />

      {/* Toast Notifications */}
      <ToastContainer toasts={toast.toasts} onDismiss={toast.dismiss} />
    </Sidebar>
  );
}
