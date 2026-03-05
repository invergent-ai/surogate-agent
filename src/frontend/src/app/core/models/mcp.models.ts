export interface McpToolInfo {
  name: string;
  description: string;
}

export interface McpServer {
  name: string;
  repo_url: string;
  start_command: string;
  cwd: string;
  transport: string;
  host: string;
  port: number;
  tools: McpToolInfo[];
  status: string;
  registered_at: string;
}
