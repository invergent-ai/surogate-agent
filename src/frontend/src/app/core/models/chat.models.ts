export interface ThinkingBlock {
  type: 'thinking';
  text: string;
  collapsed: boolean;
}

export interface SubagentActivityItem {
  type: 'thinking' | 'tool_call' | 'text';
  text?: string;
  name?: string;
  args?: Record<string, unknown>;
  result?: string;
}

export interface SubagentActivity {
  subagent: string;
  items: SubagentActivityItem[];
}

export interface ToolBlock {
  type: 'tool_call';
  name: string;
  args: Record<string, unknown>;
  result?: string;
  collapsed: boolean;
  subagentActivity?: SubagentActivity;
}

export interface TextBlock {
  type: 'text';
  text: string;
  /** True once a tool_call block has been pushed after this block in the same
   *  message turn — marks it as an intermediary "thinking out loud" fragment. */
  intermediary?: boolean;
}

export interface ErrorBlock {
  type: 'error';
  text: string;
}

export type MessageBlock = ThinkingBlock | ToolBlock | TextBlock | ErrorBlock;

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  blocks: MessageBlock[];
  timestamp: Date;
  finalized: boolean;
}

export interface SseThinkingData { text: string; }
export interface SseToolCallData { name: string; args: Record<string, unknown>; }
export interface SseToolResultData { name: string; result: string; }
export interface SseTextData { text: string; }
export interface SseDoneData { session_id: string; files: string[]; }
export interface SseErrorData { detail: string; }
export interface SseSkillUseData { name: string; description: string; }
export interface SseSubagentActivityData { subagent: string; items: SubagentActivityItem[]; partial?: boolean; }

export type SseEvent =
  | { event: 'thinking';           data: SseThinkingData }
  | { event: 'tool_call';          data: SseToolCallData }
  | { event: 'tool_result';        data: SseToolResultData }
  | { event: 'text';               data: SseTextData }
  | { event: 'done';               data: SseDoneData }
  | { event: 'error';              data: SseErrorData }
  | { event: 'skill_use';          data: SseSkillUseData }
  | { event: 'subagent_activity';  data: SseSubagentActivityData };

export interface ChatRequest {
  message: string;
  role: 'developer' | 'user';
  session_id?: string;
  skill?: string;
  model?: string;
  user_id?: string;
  allow_execute?: boolean;
  api_key?: string;
  vllm_url?: string;
  vllm_tool_calling?: boolean;
  vllm_temperature?: number | null;
  vllm_top_k?: number | null;
  vllm_top_p?: number | null;
  vllm_min_p?: number | null;
  vllm_presence_penalty?: number | null;
  vllm_context_length?: number | null;
  thinking_enabled?: boolean;
  thinking_budget?: number;
}
