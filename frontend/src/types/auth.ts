export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string | null;
  role?: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at?: string;
  updated_at?: string | null;
}

