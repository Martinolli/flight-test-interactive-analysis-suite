import { useEffect, useState } from 'react';
import { Search, Plus, Plane, Calendar } from 'lucide-react';
import Sidebar from '../components/Sidebar';
import { ApiService, FlightTest } from '../services/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';

export default function Dashboard() {
  const [flightTests, setFlightTests] = useState<FlightTest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadFlightTests();
  }, []);

  const loadFlightTests = async () => {
    try {
      setIsLoading(true);
      const tests = await ApiService.getFlightTests();
      setFlightTests(tests);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load flight tests');
    } finally {
      setIsLoading(false);
    }
  };

  const filteredTests = flightTests.filter(test =>
    test.test_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    test.aircraft_type.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  return (
    <Sidebar>
      <div className="p-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Flight Tests</h1>
          <p className="text-gray-600">Manage and analyze your flight test data</p>
        </div>

        {/* Search and Actions */}
        <div className="flex items-center justify-between mb-6">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <Input
              type="text"
              placeholder="Search flight tests..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>
          <Button className="ml-4">
            <Plus className="w-4 h-4 mr-2" />
            New Flight Test
          </Button>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
            <p className="text-gray-600">Loading flight tests...</p>
          </div>
        )}

        {/* Error State */}
        {error && !isLoading && (
          <div className="text-center py-12">
            <div className="text-red-600 mb-4">{error}</div>
            <Button onClick={loadFlightTests} variant="outline">
              Try Again
            </Button>
          </div>
        )}

        {/* Flight Tests Grid */}
        {!isLoading && !error && filteredTests.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredTests.map((test) => (
              <Card key={test.id} className="hover:shadow-lg transition-shadow cursor-pointer">
                <CardHeader>
                  <div className="flex items-start justify-between mb-2">
                    <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                      <Plane className="w-5 h-5 text-blue-600" />
                    </div>
                    <Badge variant="secondary">
                      {test.id}
                    </Badge>
                  </div>
                  <CardTitle className="text-lg">{test.test_name}</CardTitle>
                  <CardDescription className="flex items-center text-sm">
                    <Calendar className="w-4 h-4 mr-1" />
                    {formatDate(test.test_date)}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600">Aircraft:</span>
                      <span className="font-medium">{test.aircraft_type}</span>
                    </div>
                    {test.description && (
                      <p className="text-gray-600 line-clamp-2 mt-2">{test.description}</p>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && filteredTests.length === 0 && (
          <div className="text-center py-12">
            <Plane className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No flight tests found</h3>
            <p className="text-gray-600 mb-6">
              {searchQuery ? 'Try adjusting your search' : 'Get started by creating your first flight test'}
            </p>
            {!searchQuery && (
              <Button>
                <Plus className="w-4 h-4 mr-2" />
                Create Flight Test
              </Button>
            )}
          </div>
        )}
      </div>
    </Sidebar>
  );
}
