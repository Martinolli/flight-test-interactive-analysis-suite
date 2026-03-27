import { useEffect, useState } from 'react';
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
} from 'lucide-react';
import Sidebar from '../components/Sidebar';
import FlightTestModal from '../components/FlightTestModal';
import { ConfirmDialog } from '../components/ui/confirm-dialog';
import { ToastContainer, useToast } from '../components/ui/toast';
import { ApiService, FlightTest } from '../services/api';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';

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

            {/* Parameters placeholder */}
            <Card className="mt-4">
              <CardHeader>
                <CardTitle className="text-base">Parameters & Data</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="border-2 border-dashed border-gray-200 rounded-lg p-8 text-center">
                  <p className="text-gray-400 text-sm">
                    Parameter visualization will appear here once data is uploaded.
                  </p>
                </div>
              </CardContent>
            </Card>
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
