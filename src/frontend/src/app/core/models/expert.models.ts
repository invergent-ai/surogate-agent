export interface Expert {
  id: number;
  user_id: number;
  name: string;
  description: string;
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
  available_tools: string[];
  available_skills: string[];
  available_mcp_servers: string[];
  created_at: string;
}

export interface ExpertCreateRequest {
  name: string;
  description: string;
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
  available_tools: string[];
  available_skills: string[];
  available_mcp_servers: string[];
}

export function emptyExpertRequest(): ExpertCreateRequest {
  return {
    name: '',
    description: '',
    model: '',
    api_key: '',
    openrouter_provider: '',
    vllm_url: '',
    vllm_tool_calling: true,
    vllm_temperature: null,
    vllm_top_k: null,
    vllm_top_p: null,
    vllm_min_p: null,
    vllm_presence_penalty: null,
    vllm_context_length: null,
    thinking_enabled: false,
    thinking_budget: 10000,
    available_tools: [],
    available_skills: [],
    available_mcp_servers: [],
  };
}
