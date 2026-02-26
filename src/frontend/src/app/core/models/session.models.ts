export interface FileInfo {
  name: string;
  size_bytes: number;
}

/** Client-side session metadata (camelCase for component use). */
export interface SessionMeta {
  sessionId: string;
  name: string;
  createdAt: string; // ISO date string
}

/** API response shape for session metadata (snake_case from backend). */
export interface SessionMetaResponse {
  session_id: string;
  name: string;
  created_at: string;
}

/** API response shape for chat history. */
export interface ChatHistoryResponse {
  session_id: string;
  messages: unknown[];
}

export interface SessionResponse {
  session_id: string;
  workspace_dir: string;
  files: FileInfo[];
}

export interface WorkspaceResponse {
  skill: string;
  workspace_dir: string;
  files: FileInfo[];
}
