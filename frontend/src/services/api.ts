import { AuthService } from './auth';

const API_BASE_URL = 'http://localhost:8000';

// ─── Types ───────────────────────────────────────────────────────────────────

export interface FlightTest {
  id: number;
  test_name: string;
  aircraft_type: string;
  test_date: string;
  duration_seconds: number | null;
  description: string | null;
  created_by_id: number;
  created_at: string;
  updated_at: string | null;
}

export interface CreateFlightTestData {
  test_name: string;
  aircraft_type: string;
  test_date: string;
  description?: string;
}

export interface UploadRecord {
  id: number;
  flight_test_id: number;
  filename: string;
  file_type: 'csv' | 'excel';
  row_count: number | null;
  status: 'pending' | 'processing' | 'success' | 'failed';
  error_message: string | null;
  uploaded_by_id: number;
  created_at: string;
}

export interface UploadResponse {
  upload_id: number;
  filename: string;
  row_count: number;
  columns: string[];
  preview: Record<string, unknown>[];
  message: string;
}

export interface ParameterInfo {
  name: string;
  unit: string | null;
  data_type: string;
  sample_count: number;
  min_value: number | null;
  max_value: number | null;
  mean_value: number | null;
}

export interface ParameterDataPoint {
  timestamp: string;
  value: number;
}

export interface ParameterSeries {
  parameter_name: string;
  unit: string | null;
  data: ParameterDataPoint[];
  statistics: {
    min: number;
    max: number;
    mean: number;
    std_dev: number;
    count: number;
  };
}

// ─── Service ─────────────────────────────────────────────────────────────────

export class ApiService {
  private static async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = AuthService.getAccessToken();

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || `Request failed with status ${response.status}`);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  // ─── Flight Tests ──────────────────────────────────────────────────────────

  static async getFlightTests(): Promise<FlightTest[]> {
    return this.request<FlightTest[]>('/api/flight-tests');
  }

  static async getFlightTest(id: number): Promise<FlightTest> {
    return this.request<FlightTest>(`/api/flight-tests/${id}`);
  }

  static async createFlightTest(data: CreateFlightTestData): Promise<FlightTest> {
    return this.request<FlightTest>('/api/flight-tests', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async updateFlightTest(
    id: number,
    data: Partial<CreateFlightTestData>
  ): Promise<FlightTest> {
    return this.request<FlightTest>(`/api/flight-tests/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  static async deleteFlightTest(id: number): Promise<void> {
    return this.request<void>(`/api/flight-tests/${id}`, {
      method: 'DELETE',
    });
  }

  // ─── File Upload ───────────────────────────────────────────────────────────

  static uploadFile(
    flightTestId: number,
    file: File,
    onProgress: (percent: number) => void
  ): Promise<UploadResponse> {
    return new Promise((resolve, reject) => {
      const token = AuthService.getAccessToken();
      const formData = new FormData();
      formData.append('file', file);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE_URL}/api/flight-tests/${flightTestId}/upload`);

      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      }

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch {
            resolve({ message: 'Upload successful' } as UploadResponse);
          }
        } else {
          try {
            const err = JSON.parse(xhr.responseText);
            reject(new Error(err.detail || `Upload failed with status ${xhr.status}`));
          } catch {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        }
      });

      xhr.addEventListener('error', () => reject(new Error('Network error during upload')));
      xhr.addEventListener('abort', () => reject(new Error('Upload was cancelled')));

      xhr.send(formData);
    });
  }

  static async getUploadHistory(flightTestId: number): Promise<UploadRecord[]> {
    return this.request<UploadRecord[]>(`/api/flight-tests/${flightTestId}/uploads`);
  }

  static async getAllUploads(): Promise<UploadRecord[]> {
    return this.request<UploadRecord[]>('/api/uploads');
  }

  // ─── Parameters ────────────────────────────────────────────────────────────

  /**
   * List all available parameters for a given flight test.
   */
  static async getParameters(flightTestId: number): Promise<ParameterInfo[]> {
    return this.request<ParameterInfo[]>(`/api/flight-tests/${flightTestId}/parameters`);
  }

  /**
   * Fetch time-series data for one or more parameters.
   * paramNames is a comma-separated list, e.g. "altitude,airspeed"
   */
  static async getParameterData(
    flightTestId: number,
    paramNames: string[]
  ): Promise<ParameterSeries[]> {
    const query = paramNames.map((n) => `parameters=${encodeURIComponent(n)}`).join('&');
    return this.request<ParameterSeries[]>(
      `/api/flight-tests/${flightTestId}/parameters/data?${query}`
    );
  }
}
