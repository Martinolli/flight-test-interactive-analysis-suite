/**
 * API Service
 * Handles all API calls to the backend
 */

import { AuthService } from './auth';

const API_BASE_URL = 'http://localhost:8000';

export interface FlightTest {
  id: number;
  test_name: string;
  aircraft_type: string;
  test_date: string;
  description: string | null;
  status: 'draft' | 'in_progress' | 'completed' | 'archived';
  created_at: string;
  updated_at: string | null;
  user_id: number;
}

export class ApiService {
  /**
   * Make authenticated API request
   */
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

    return response.json();
  }

  /**
   * Get all flight tests
   */
  static async getFlightTests(): Promise<FlightTest[]> {
    return this.request<FlightTest[]>('/api/flight-tests');
  }

  /**
   * Get single flight test by ID
   */
  static async getFlightTest(id: number): Promise<FlightTest> {
    return this.request<FlightTest>(`/api/flight-tests/${id}`);
  }

  /**
   * Create new flight test
   */
  static async createFlightTest(data: {
    test_name: string;
    aircraft_type: string;
    test_date: string;
    description?: string;
    status?: string;
  }): Promise<FlightTest> {
    return this.request<FlightTest>('/api/flight-tests', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /**
   * Update flight test
   */
  static async updateFlightTest(
    id: number,
    data: Partial<FlightTest>
  ): Promise<FlightTest> {
    return this.request<FlightTest>(`/api/flight-tests/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  /**
   * Delete flight test
   */
  static async deleteFlightTest(id: number): Promise<void> {
    return this.request<void>(`/api/flight-tests/${id}`, {
      method: 'DELETE',
    });
  }
}
