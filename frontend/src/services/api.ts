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
  file_type: 'csv';
  source_format?: string;
  row_count: number | null;
  status: 'pending' | 'processing' | 'success' | 'failed';
  error_message: string | null;
  error_log?: string | null;
  uploaded_by_id: number;
  created_at: string;
  updated_at?: string | null;
}

export interface UploadResponse {
  message: string;
  filename?: string;
  rows_processed: number;
  data_points_created: number;
  previous_data_points_deleted?: number;
  session_id?: number;
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
  source_id?: string;
  filename: string;
  title: string | null;
  page_numbers: string | null;
  section_title: string | null;
  similarity: number;
}

export interface QueryCoverage {
  citation_density: number;
  warning_threshold: number;
  repair_threshold: number;
  has_inline_citations: boolean;
  retrieved_sources_count: number;
  cited_sources_count: number;
  unique_documents_retrieved: number;
  unique_documents_cited: number;
}

export interface QueryRetrievalMetadata {
  requested_top_k: number;
  context_limit: number;
  vector_candidates: number;
  lexical_candidates: number;
  min_unique_documents: number;
  max_chunks_per_document: number;
}

export interface QueryResponse {
  answer: string;
  summary?: string | null;
  answer_type?: string;
  technical_scope?: string;
  assumptions?: string[];
  limitations?: string[];
  calculation_notes?: string[];
  recommended_next_queries?: string[];
  sources: QuerySource[];
  warnings?: string[];
  coverage?: QueryCoverage;
  retrieval_metadata?: QueryRetrievalMetadata;
}

export interface AIAnalysisResponse {
  analysis: string;
  flight_test_name: string;
  parameters_analysed: number;
  analysis_job_id: number;
  model_name: string;
  model_version?: string | null;
  output_sha256: string;
  created_at: string;
  retrieved_source_ids: string[];
}

export interface AnalysisJobResponse {
  id: number;
  flight_test_id: number;
  flight_test_name: string;
  parameters_analysed: number;
  status: string;
  model_name: string;
  model_version?: string | null;
  prompt_text: string;
  analysis: string;
  output_sha256: string;
  created_at: string;
  updated_at?: string | null;
  retrieved_source_ids: string[];
  parameter_stats_snapshot: Array<{
    name: string;
    unit?: string | null;
    min_val?: number | null;
    max_val?: number | null;
    avg_val?: number | null;
    std_val?: number | null;
    sample_count: number;
  }>;
  retrieved_sources_snapshot: Array<{
    source_id?: string;
    filename?: string;
    title?: string;
    page_numbers?: string;
    section_title?: string;
    similarity?: number;
    excerpt?: string;
  }>;
}

// ─── Admin Types ──────────────────────────────────────────────────────────────

export interface AdminUser {
  id: number;
  username: string;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface AdminUserUpdate {
  full_name?: string | null;
  email?: string;
  is_active?: boolean;
  is_superuser?: boolean;
  new_password?: string;
}

export interface AdminUserCreate {
  username: string;
  email: string;
  password: string;
  full_name?: string;
  is_superuser?: boolean;
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

  static async getUploadHistory(flightTestId: number): Promise<UploadRecord[]> {
    return this.request<UploadRecord[]>(`/api/flight-tests/${flightTestId}/ingestion-sessions`);
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
    topK = 8
  ): Promise<QueryResponse> {
    return this.request<QueryResponse>('/api/documents/query', {
      method: 'POST',
      body: JSON.stringify({ question, top_k: topK }),
    });
  }

  // ─── AI Analysis ──────────────────────────────────────────────────────────

  static async getAIAnalysis(
    flightTestId: number,
    userPrompt?: string
  ): Promise<AIAnalysisResponse> {
    return this.request<AIAnalysisResponse>(
      `/api/documents/flight-tests/${flightTestId}/ai-analysis`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_prompt: userPrompt ?? null }),
      }
    );
  }

  static async getAIAnalysisJob(
    flightTestId: number,
    analysisJobId: number
  ): Promise<AnalysisJobResponse> {
    return this.request<AnalysisJobResponse>(
      `/api/documents/flight-tests/${flightTestId}/ai-analysis/jobs/${analysisJobId}`
    );
  }

  // ─── PDF Export ───────────────────────────────────────────────────────────

  static async exportAnalysisPDF(
    flightTestId: number,
    analysisJobId: number
  ): Promise<Blob> {
    const token = AuthService.getAccessToken();
    const response = await fetch(
      `${API_BASE_URL}/api/admin/flight-tests/${flightTestId}/report.pdf`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token && { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify({ analysis_job_id: analysisJobId }),
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: 'PDF export failed' }));
      throw new Error(err.detail || `PDF export failed with status ${response.status}`);
    }
    return response.blob();
  }

  // ─── Admin: User Management ───────────────────────────────────────────────

  static async adminListUsers(): Promise<AdminUser[]> {
    return this.request<AdminUser[]>('/api/admin/users');
  }

  static async adminUpdateUser(
    userId: number,
    update: AdminUserUpdate
  ): Promise<AdminUser> {
    return this.request<AdminUser>(`/api/admin/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify(update),
    });
  }

  static async adminCreateUser(data: AdminUserCreate): Promise<AdminUser> {
    return this.request<AdminUser>('/api/admin/users', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async adminDeleteUser(userId: number): Promise<void> {
    return this.request<void>(`/api/admin/users/${userId}`, { method: 'DELETE' });
  }
}
