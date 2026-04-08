export interface HumanTask {
  id: string;
  taskType: 'approval' | 'report' | 'file_request' | 'form_input';
  status: 'pending' | 'completed' | 'cancelled';
  title: string;
  description: string;
  context: Record<string, unknown>;
  assignedTo: string;
  assignedBy: string;
  createdAt: string;
  respondedAt?: string;
  response?: TaskResponse;
}

export interface TaskResponse {
  decision?: 'approved' | 'rejected';
  acknowledged?: boolean;
  feedback?: string;
  cancelled?: boolean;
  form_data?: Record<string, unknown>;
  files?: string[];
}

export interface TaskRespondPayload {
  decision?: 'approved' | 'rejected';
  acknowledged?: boolean;
  feedback?: string;
}

// Raw API response shape (snake_case from backend)
export interface HumanTaskRaw {
  id: string;
  task_type: string;
  status: string;
  title: string;
  description: string;
  context: Record<string, unknown>;
  assigned_to: string;
  assigned_by: string;
  created_at: string;
  responded_at?: string;
  response?: TaskResponse;
}

export function mapTask(raw: HumanTaskRaw): HumanTask {
  return {
    id: raw.id,
    taskType: raw.task_type as 'approval' | 'report' | 'file_request' | 'form_input',
    status: raw.status as 'pending' | 'completed' | 'cancelled',
    title: raw.title,
    description: raw.description,
    context: raw.context ?? {},
    assignedTo: raw.assigned_to,
    assignedBy: raw.assigned_by,
    createdAt: raw.created_at,
    respondedAt: raw.responded_at,
    response: raw.response,
  };
}
