export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  role: 'developer' | 'user';
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: number;
  username: string;
  email: string;
  role: 'developer' | 'user';
  is_active: boolean;
  created_at: string;
}

export interface UserInfo {
  username: string;
  role: 'developer' | 'user';
  exp: number;
}
