import { useState, useEffect } from 'react';
import { Dialog } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { ApiService, FlightTest, CreateFlightTestData } from '../services/api';

interface FlightTestModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (test: FlightTest) => void;
  editingTest?: FlightTest | null;
}

interface FormData {
  test_name: string;
  aircraft_type: string;
  test_date: string;
  description: string;
}

interface FormErrors {
  test_name?: string;
  aircraft_type?: string;
  test_date?: string;
}

export default function FlightTestModal({
  open,
  onClose,
  onSuccess,
  editingTest,
}: FlightTestModalProps) {
  const isEditing = !!editingTest;

  const [formData, setFormData] = useState<FormData>({
    test_name: '',
    aircraft_type: '',
    test_date: new Date().toISOString().split('T')[0],
    description: '',
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');

  // Populate form when editing
  useEffect(() => {
    if (editingTest) {
      setFormData({
        test_name: editingTest.test_name,
        aircraft_type: editingTest.aircraft_type,
        test_date: editingTest.test_date.split('T')[0],
        description: editingTest.description || '',
      });
    } else {
      setFormData({
        test_name: '',
        aircraft_type: '',
        test_date: new Date().toISOString().split('T')[0],
        description: '',
      });
    }
    setErrors({});
    setSubmitError('');
  }, [editingTest, open]);

  const validate = (): boolean => {
    const newErrors: FormErrors = {};
    if (!formData.test_name.trim()) {
      newErrors.test_name = 'Test name is required';
    } else if (formData.test_name.trim().length < 3) {
      newErrors.test_name = 'Test name must be at least 3 characters';
    }
    if (!formData.aircraft_type.trim()) {
      newErrors.aircraft_type = 'Aircraft type is required';
    }
    if (!formData.test_date) {
      newErrors.test_date = 'Test date is required';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleChange = (field: keyof FormData, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (errors[field as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [field]: undefined }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setIsSubmitting(true);
    setSubmitError('');

    try {
      const payload: CreateFlightTestData = {
        test_name: formData.test_name.trim(),
        aircraft_type: formData.aircraft_type.trim(),
        test_date: formData.test_date,
        description: formData.description.trim() || undefined,
      };

      let result: FlightTest;
      if (isEditing && editingTest) {
        result = await ApiService.updateFlightTest(editingTest.id, payload);
      } else {
        result = await ApiService.createFlightTest(payload);
      }

      onSuccess(result);
      onClose();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'An unexpected error occurred');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={isEditing ? 'Edit Flight Test' : 'New Flight Test'}
      description={
        isEditing
          ? 'Update the details of this flight test.'
          : 'Fill in the details to create a new flight test record.'
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        {/* Test Name */}
        <div className="space-y-1.5">
          <label htmlFor="test_name" className="block text-sm font-medium text-gray-700">
            Test Name <span className="text-red-500">*</span>
          </label>
          <Input
            id="test_name"
            type="text"
            placeholder="e.g. High Altitude Endurance Test"
            value={formData.test_name}
            onChange={(e) => handleChange('test_name', e.target.value)}
            className={errors.test_name ? 'border-red-400 focus:ring-red-400' : ''}
            disabled={isSubmitting}
          />
          {errors.test_name && (
            <p className="text-xs text-red-500">{errors.test_name}</p>
          )}
        </div>

        {/* Aircraft Type */}
        <div className="space-y-1.5">
          <label htmlFor="aircraft_type" className="block text-sm font-medium text-gray-700">
            Aircraft Type <span className="text-red-500">*</span>
          </label>
          <Input
            id="aircraft_type"
            type="text"
            placeholder="e.g. Cessna 172, Boeing 737"
            value={formData.aircraft_type}
            onChange={(e) => handleChange('aircraft_type', e.target.value)}
            className={errors.aircraft_type ? 'border-red-400 focus:ring-red-400' : ''}
            disabled={isSubmitting}
          />
          {errors.aircraft_type && (
            <p className="text-xs text-red-500">{errors.aircraft_type}</p>
          )}
        </div>

        {/* Test Date */}
        <div className="space-y-1.5">
          <label htmlFor="test_date" className="block text-sm font-medium text-gray-700">
            Test Date <span className="text-red-500">*</span>
          </label>
          <Input
            id="test_date"
            type="date"
            value={formData.test_date}
            onChange={(e) => handleChange('test_date', e.target.value)}
            className={errors.test_date ? 'border-red-400 focus:ring-red-400' : ''}
            disabled={isSubmitting}
          />
          {errors.test_date && (
            <p className="text-xs text-red-500">{errors.test_date}</p>
          )}
        </div>

        {/* Description */}
        <div className="space-y-1.5">
          <label htmlFor="description" className="block text-sm font-medium text-gray-700">
            Description <span className="text-gray-400 font-normal">(optional)</span>
          </label>
          <Textarea
            id="description"
            placeholder="Describe the objectives, conditions, or notes for this test..."
            value={formData.description}
            onChange={(e) => handleChange('description', e.target.value)}
            rows={3}
            disabled={isSubmitting}
          />
        </div>

        {/* Submit Error */}
        {submitError && (
          <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3">
            <p className="text-sm text-red-600">{submitError}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 pt-2">
          <Button
            type="button"
            variant="outline"
            className="flex-1"
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            className="flex-1"
            disabled={isSubmitting}
          >
            {isSubmitting
              ? isEditing ? 'Saving...' : 'Creating...'
              : isEditing ? 'Save Changes' : 'Create Flight Test'}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
