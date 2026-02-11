import type { TokenResponse, User } from '../types/auth';

const API_BASE_URL = 'http://localhost:8000';

export class AuthService {
  static async login(username: string, password: string ): Promise<TokenResponse> {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(error.detail || 'Login failed');
    }

    const data: TokenResponse = await response.json();

    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    localStorage.setItem('token_expiry', String(Date.now() + (30 * 60 * 1000)));

    return data;
  }

  static async logout(): Promise<void> {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('token_expiry');
  }

  static async getCurrentUser(): Promise<User> {
    const token = this.getAccessToken();

    if (!token) {
      throw new Error('No access token');
    }

    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error('Failed to get current user');
    }

    return response.json();
  }

  static getAccessToken(): string | null {
    const token = localStorage.getItem('access_token');
    const expiry = localStorage.getItem('token_expiry');

    if (!token || !expiry) {
      return null;
    }

    if (Date.now() >= parseInt(expiry)) {
      return null;
    }

    return token;
  }

  static isAuthenticated(): boolean {
    return this.getAccessToken() !== null;
  }
}
