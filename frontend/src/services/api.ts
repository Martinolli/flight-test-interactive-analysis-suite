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
  message: string;
  filename?: string;
  rows_processed: number;
  data_points_created: number;
  previous_data_points_deleted?: number;
  // convenience alias so callers can use row_count uniformly
  row_count?: number;
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

// ─── Document / RAG Types ───────────────────────────────────────────────────

export interface Document {
  id: number;
  filename: string;
  title: string | null;
  doc_type: string | null;
  description: string | null;
  total_pages: number | null;
  total_chunks: number | null;
  file_size_bytes: number | null;
  status: 'processing' | 'ready' | 'error';
  error_message: string | null;
  created_at: string;
}

export interface QuerySource {
  filename: string;
  title: string | null;
  page_numbers: string | null;
  section_title: string | null;
  similarity: number;
}

export interface QueryResponse {
  answer: string;
  sources: QuerySource[];
}

export interface AIAnalysisResponse {
  analysis: string;
  flight_test_name: string;
  parameters_analysed: number;
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
      xhr.open('POST', `${API_BASE_URL}/api/flight-tests/${flightTestId}/upload-csv`);

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

  /**
   * Derive upload history from the parameters endpoint.
   * Each distinct parameter group represents an upload session.
   * Returns a synthetic UploadRecord so the UI renders without a dedicated endpoint.
   */
  static async getUploadHistory(flightTestId: number): Promise<UploadRecord[]> {
    try {
      const params = await this.request<ParameterInfo[]>(
        `/api/flight-tests/${flightTestId}/parameters`
      );
      if (!params || params.length === 0) return [];
      // Use the sample_count of the first parameter as a proxy for CSV rows
      // (each row produces one data point per parameter, so any single parameter's
      // sample_count equals the number of CSV data rows)
      const csvRowCount = params[0]?.sample_count ?? 0;
      const storedFilename = localStorage.getItem(`upload_filename_${flightTestId}`) || 'Uploaded data';
      const storedDate = localStorage.getItem(`upload_date_${flightTestId}`) || new Date().toISOString();
      return [
        {
          id: flightTestId,
          flight_test_id: flightTestId,
          filename: storedFilename,
          file_type: 'csv',
          row_count: csvRowCount,
          status: 'success',
          error_message: null,
          uploaded_by_id: 0,
          created_at: storedDate,
        },
      ];
    } catch {
      return [];
    }
  }

  static async getAllUploads(): Promise<UploadRecord[]> {
    return [];
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

  // ─── Document Library ─────────────────────────────────────────────────────

  static async getDocuments(): Promise<Document[]> {
    return this.request<Document[]>('/api/documents/');
  }

  static uploadDocument(
    file: File,
    meta: { title?: string; doc_type?: string; description?: string },
    onProgress: (percent: number) => void
  ): Promise<Document> {
    return new Promise((resolve, reject) => {
      const token = AuthService.getAccessToken();
      const formData = new FormData();
      formData.append('file', file);
      if (meta.title) formData.append('title', meta.title);
      if (meta.doc_type) formData.append('doc_type', meta.doc_type);
      if (meta.description) formData.append('description', meta.description);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE_URL}/api/documents/upload`);
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try { resolve(JSON.parse(xhr.responseText)); }
          catch { reject(new Error('Invalid response from server')); }
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
      xhr.addEventListener('abort', () => reject(new Error('Upload cancelled')));
      xhr.send(formData);
    });
  }

  static async deleteDocument(docId: number): Promise<void> {
    return this.request<void>(`/api/documents/${docId}`, { method: 'DELETE' });
  }

  static async queryDocuments(
    question: string,
    topK = 6
  ): Promise<QueryResponse> {
    return this.request<QueryResponse>('/api/documents/query', {
      method: 'POST',
      body: JSON.stringify({ question, top_k: topK }),
    });
  }

  // ─── AI Analysis ──────────────────────────────────────────────────────────

  static async getAIAnalysis(flightTestId: number): Promise<AIAnalysisResponse> {
    return this.request<AIAnalysisResponse>(
      `/api/documents/flight-tests/${flightTestId}/ai-analysis`,
      { method: 'POST' }
    );
  }
}
