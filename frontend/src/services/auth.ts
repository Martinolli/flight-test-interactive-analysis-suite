/**
 * Authentication Service
 * Handles all authentication operations with the backend API
 */

import type { TokenResponse, User } from '../types/auth';

const API_BASE_URL = 'http://localhost:8000';

export class AuthService {
  /**
   * Login with email and password
   * Stores tokens in localStorage on success
   */
    static async login(email: string, password: string): Promise<TokenResponse> {
    // Create URL-encoded form data (FastAPI OAuth2 expects this format)
    const formBody = new URLSearchParams();
    formBody.append('username', email);
    formBody.append('password', password);

    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formBody.toString(),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(error.detail || 'Login failed');
    }

    const data: TokenResponse = await response.json();

    // Store tokens in localStorage
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    localStorage.setItem('token_expiry', String(Date.now() + data.expires_in * 1000));

    return data;
  }


  /**
   * Logout - clear tokens from localStorage
   */
  static async logout(): Promise<void> {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('token_expiry');
  }

  /**
   * Refresh access token using refresh token
   */
  static async refreshToken(): Promise<TokenResponse> {
    const refreshToken = localStorage.getItem('refresh_token');

    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      throw new Error('Token refresh failed');
    }

    const data: TokenResponse = await response.json();

    // Update tokens in localStorage
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('token_expiry', String(Date.now() + data.expires_in * 1000));

    return data;
  }

  /**
   * Get current user profile
   */
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

  /**
   * Get access token from localStorage
   * Returns null if token doesn't exist or is expired
   */
  static getAccessToken(): string | null {
    const token = localStorage.getItem('access_token');
    const expiry = localStorage.getItem('token_expiry');

    if (!token || !expiry) {
      return null;
    }

    // Check if token is expired
    if (Date.now() >= parseInt(expiry)) {
      return null;
    }

    return token;
  }

  /**
   * Check if user is authenticated
   */
  static isAuthenticated(): boolean {
    return this.getAccessToken() !== null;
  }
}
