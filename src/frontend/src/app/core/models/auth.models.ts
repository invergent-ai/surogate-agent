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
  model: string;
  api_key: string;
  openrouter_provider: string;
  vllm_url: string;
  vllm_tool_calling: boolean;
  vllm_temperature: number | null;
  vllm_top_k: number | null;
  vllm_top_p: number | null;
  vllm_min_p: number | null;
  vllm_presence_penalty: number | null;
  vllm_context_length: number | null;
  thinking_enabled: boolean;
  thinking_budget: number;
}

export interface UserInfo {
  username: string;
  role: 'developer' | 'user';
  exp: number;
}
