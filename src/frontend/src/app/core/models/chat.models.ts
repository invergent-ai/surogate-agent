export interface ThinkingBlock {
  type: 'thinking';
  text: string;
  collapsed: boolean;
}

export interface ToolBlock {
  type: 'tool_call';
  name: string;
  args: Record<string, unknown>;
  result?: string;
  collapsed: boolean;
}

export interface TextBlock {
  type: 'text';
  text: string;
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

export type SseEvent =
  | { event: 'thinking';    data: SseThinkingData }
  | { event: 'tool_call';   data: SseToolCallData }
  | { event: 'tool_result'; data: SseToolResultData }
  | { event: 'text';        data: SseTextData }
  | { event: 'done';        data: SseDoneData }
  | { event: 'error';       data: SseErrorData };

export interface ChatRequest {
  message: string;
  role: 'developer' | 'user';
  session_id?: string;
  skill?: string;
  model?: string;
  user_id?: string;
  allow_execute?: boolean;
  api_key?: string;
}
