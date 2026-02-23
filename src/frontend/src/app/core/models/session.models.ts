export interface FileInfo {
  name: string;
  size_bytes: number;
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
