export interface SkillListItem {
  name: string;
  description: string;
  version: string;
  role_restriction: string | null;
  path: string;
}

export interface FileInfo {
  name: string;
  size_bytes: number;
}

export interface SkillResponse {
  name: string;
  description: string;
  version: string;
  role_restriction: string | null;
  allowed_tools: string[];
  path: string;
  skill_md_content: string;
  helper_files: FileInfo[];
}

export interface SkillCreateRequest {
  name: string;
  description: string;
  role_restriction?: string | null;
  allowed_tools?: string[];
  version?: string;
  skill_md_body?: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}
