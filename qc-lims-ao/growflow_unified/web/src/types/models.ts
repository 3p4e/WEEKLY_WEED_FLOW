/* Planner API shapes — mirror server/planner_api/schemas.py.
   Hand-authored; can be regenerated from the API's OpenAPI later. */

export type TaskStatus = "pending" | "working" | "review" | "stuck" | "postponed" | "done";
export type TaskPriority = "critical" | "high" | "medium" | "low";
export type Role = "operator" | "hod" | "qa" | "qp" | "executive" | "admin";
export type Lang = "en" | "mk";

export interface UserOut {
  id: string;
  username: string;
  full_name: string;
  role: Role;
  email?: string | null;
  avatar_url?: string | null;
  dept_id?: string | null;
  dept_key?: string | null;
  must_change_password?: boolean;
  cross_department?: boolean;
}

export type NodeKind = "task" | "annex" | "step";

export interface PlannerTreeNode {
  id: string;
  parent_id?: string | null;
  title: string;
  node_kind: NodeKind;
  status: TaskStatus;
  priority: TaskPriority;
  is_sop: boolean;
  annex_count: number;
  owner_name?: string | null;
  department_key?: string | null;
  attributes: Record<string, unknown>;
  started_at?: string | null;
  ended_at?: string | null;
  children: PlannerTreeNode[];
}

export interface ChangeProposal {
  id: string;
  proposed_by: string;
  kind: string;
  target?: string | null;
  payload: Record<string, unknown>;
  rationale: string;
  evidence: Record<string, unknown>;
  status: "pending" | "approved" | "rejected" | "applied";
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  created_at?: string | null;
}

export interface FieldRegistryEntry {
  key: string;
  label_en: string;
  label_mk?: string | null;
  data_type: string;
  applies_to: string;
  status: string;
  promoted: boolean;
}

export interface AiFunctions {
  catalog: Record<string, string>;
  active: string[];
}

export interface AiResult {
  available: boolean;
  function?: string | null;
  output?: string | null;
  reason?: string | null;
}

export interface ProvisionResult {
  id: string;
  username: string;
  role: string;
  temp_password: string;
  expires_hours: number;
}

export interface AdminUser {
  id: string;
  username: string;
  full_name: string;
  role: Role;
  email?: string | null;
  dept_id?: string | null;
  dept_key?: string | null;
  is_active: boolean;
  cross_department: boolean;
  must_change_password: boolean;
  last_login_at?: string | null;
}

export interface ResetResult {
  sent: boolean;
  delivery: string;          // email | shown
  code?: string | null;
}

export interface Token {
  access_token: string;
  token_type: string;
  user: UserOut;
}

export interface PlannerDepartment {
  id: string;
  key: string;
  name_en: string;
  name_mk: string;
  icon?: string | null;
  color?: string | null;
  handoff_to_id?: string | null;
  position: number;
}

export interface PlannerSubtask {
  id?: string | null;
  text: string;
  done: boolean;
  position: number;
}

export interface PlannerProgressNote {
  id: string;
  day?: string | null;
  note: string;
  author_id?: string | null;
  author_name?: string | null;
  created_at?: string | null;
}

export interface PlannerHandoff {
  id: string;
  to_department_id: string;
  to_department_key?: string | null;
  status: string;
  requested_by?: string | null;
  created_at?: string | null;
}

export interface PlannerTask {
  id: string;
  department_id: string;
  department_key?: string | null;
  title: string;
  owner_id?: string | null;
  owner_name?: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  week_start: string;
  days: string[];
  room?: string | null;
  batch?: string | null;
  tags: string[];
  description?: string | null;
  blocker?: string | null;
  outcome?: string | null;
  assignment_status?: string;            // pending | accepted | declined
  assignment_responded_at?: string | null;
  assignment_note?: string | null;
  position: number;
  parent_id?: string | null;
  node_kind?: NodeKind;
  is_sop?: boolean;
  annex_count?: number;
  attributes?: Record<string, unknown>;
  started_at?: string | null;
  ended_at?: string | null;
  child_count?: number;
  helper_ids: string[];
  subtasks: PlannerSubtask[];
  notes: PlannerProgressNote[];
  deps: string[];
  handoffs: PlannerHandoff[];
  created_at?: string | null;
  updated_at?: string | null;
  completed_at?: string | null;
}

export interface PlannerTaskCreate {
  department_id: string;
  title: string;
  week_start: string;
  owner_id?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  days?: string[];
  room?: string | null;
  batch?: string | null;
  tags?: string[];
  description?: string | null;
  blocker?: string | null;
  outcome?: string | null;
  helper_ids?: string[];
  subtasks?: PlannerSubtask[];
  deps?: string[];
}

export type PlannerTaskUpdate = Partial<Omit<PlannerTaskCreate, "department_id" | "week_start">> & {
  department_id?: string;
  week_start?: string;
  position?: number;
};

export interface PlannerTelemetry {
  week_start: string;
  total: number;
  completion: number;
  by_status: Record<string, number>;
  busiest_day?: string | null;
}

export interface PlannerWeeklyReport {
  id: string;
  user_id: string;
  user_name?: string | null;
  week_start: string;
  completed_summary?: string | null;
  progress_summary?: string | null;
  next_week_plan?: string | null;
  status: "draft" | "submitted";
  ai_generated: boolean;
  submitted_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface PlannerWeeklyReportUpdate {
  completed_summary?: string | null;
  progress_summary?: string | null;
  next_week_plan?: string | null;
}

export interface AiDraftResult {
  available: boolean;
  completed_summary?: string | null;
  progress_summary?: string | null;
  next_week_plan?: string | null;
  note?: string | null;
}

export interface RewriteResult {
  available: boolean;
  text: string;
  note?: string | null;
}

export interface RolloverResult {
  created: number;
  target_week: string;
}

export interface ExecDeptStat {
  dept_id: string;
  dept_key: string;
  name_en: string;
  name_mk: string;
  total: number;
  done: number;
  stuck: number;
  completion: number;
}

export interface ExecUserStat {
  user_id: string;
  user_name: string;
  dept_key?: string | null;
  total: number;
  done: number;
  completion: number;
}

export interface ExecTelemetry {
  week_start: string;
  total: number;
  completion: number;
  by_status: Record<string, number>;
  busiest_day?: string | null;
  headcount: number;
  reports_submitted: number;
  by_department: ExecDeptStat[];
  by_user: ExecUserStat[];
}

export interface ExecInsight {
  available: boolean;
  summary?: string | null;
  highlights: string[];
  risks: string[];
  foresight?: string | null;
  sources: string[];
  note?: string | null;
}
