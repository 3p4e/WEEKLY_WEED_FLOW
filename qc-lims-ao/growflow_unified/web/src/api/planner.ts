/* Typed wrappers over the planner endpoints. */
import { apiDelete, apiGet, apiPatch, apiPost, apiPut, setToken } from "./client";
import type {
  AdminUser,
  AiDraftResult,
  AiFunctions,
  AiResult,
  ChangeProposal,
  ResetResult,
  ExecInsight,
  ExecTelemetry,
  FieldRegistryEntry,
  PlannerDepartment,
  PlannerTask,
  PlannerTaskCreate,
  PlannerTaskUpdate,
  PlannerTelemetry,
  PlannerTreeNode,
  PlannerWeeklyReport,
  PlannerWeeklyReportUpdate,
  ProvisionResult,
  RewriteResult,
  RolloverResult,
  Token,
  UserOut,
} from "../types/models";

/* ── Auth ─────────────────────────────────────────────────────────────────*/
export async function login(username: string, password: string): Promise<Token> {
  const t = await apiPost<Token>("/auth/login", { username, password });
  setToken(t.access_token);
  return t;
}
export const me = (): Promise<UserOut> => apiGet<UserOut>("/auth/me");
export const logout = (): void => setToken(null);

/* ── Reference ────────────────────────────────────────────────────────────*/
export const listDepartments = (): Promise<PlannerDepartment[]> =>
  apiGet<PlannerDepartment[]>("/planner/departments");
export const listUsers = (): Promise<UserOut[]> => apiGet<UserOut[]>("/planner/users");

/* ── Tasks ────────────────────────────────────────────────────────────────*/
export function listTasks(opts: {
  weekStart?: string;
  departmentId?: string;
  ownerId?: string;
} = {}): Promise<PlannerTask[]> {
  const q = new URLSearchParams();
  if (opts.weekStart) q.set("week_start", opts.weekStart);
  if (opts.departmentId) q.set("department_id", opts.departmentId);
  if (opts.ownerId) q.set("owner_id", opts.ownerId);
  const qs = q.toString();
  return apiGet<PlannerTask[]>(`/planner/tasks${qs ? `?${qs}` : ""}`);
}
export const getTask = (id: string): Promise<PlannerTask> => apiGet<PlannerTask>(`/planner/tasks/${id}`);
export const createTask = (body: PlannerTaskCreate): Promise<PlannerTask> =>
  apiPost<PlannerTask>("/planner/tasks", body);
export const updateTask = (id: string, body: PlannerTaskUpdate): Promise<PlannerTask> =>
  apiPatch<PlannerTask>(`/planner/tasks/${id}`, body);
export const deleteTask = (id: string): Promise<void> => apiDelete(`/planner/tasks/${id}`);
export const addNote = (id: string, note: string, day?: string): Promise<PlannerTask> =>
  apiPost<PlannerTask>(`/planner/tasks/${id}/notes`, { note, day: day ?? null });
export const addHandoff = (id: string, toDepartmentId: string): Promise<PlannerTask> =>
  apiPost<PlannerTask>(`/planner/tasks/${id}/handoffs`, { to_department_id: toDepartmentId });
export const respondAssignment = (id: string, decision: "accepted" | "declined", note?: string): Promise<PlannerTask> =>
  apiPost<PlannerTask>(`/planner/tasks/${id}/assignment`, { decision, note: note ?? null });

/* ── Telemetry ────────────────────────────────────────────────────────────*/
export const getTelemetry = (weekStart: string): Promise<PlannerTelemetry> =>
  apiGet<PlannerTelemetry>(`/planner/telemetry?week_start=${weekStart}`);

/* ── Weekly reports + AI ──────────────────────────────────────────────────*/
export const getReport = (weekStart: string): Promise<PlannerWeeklyReport> =>
  apiGet<PlannerWeeklyReport>(`/planner/reports?week_start=${weekStart}`);
export const saveReport = (weekStart: string, body: PlannerWeeklyReportUpdate): Promise<PlannerWeeklyReport> =>
  apiPut<PlannerWeeklyReport>(`/planner/reports?week_start=${weekStart}`, body);
export const submitReport = (weekStart: string, body: PlannerWeeklyReportUpdate): Promise<PlannerWeeklyReport> =>
  apiPost<PlannerWeeklyReport>(`/planner/reports/submit?week_start=${weekStart}`, body);
export const aiDraftReport = (weekStart: string): Promise<AiDraftResult> =>
  apiPost<AiDraftResult>(`/planner/reports/ai-draft?week_start=${weekStart}`);
export const rolloverWeek = (weekStart: string): Promise<RolloverResult> =>
  apiPost<RolloverResult>(`/planner/reports/rollover?week_start=${weekStart}`);
export const aiRewrite = (text: string, tone = "concise"): Promise<RewriteResult> =>
  apiPost<RewriteResult>("/planner/ai/rewrite", { text, tone });

/* ── Executive analytics ──────────────────────────────────────────────────*/
export const getExecTelemetry = (weekStart: string): Promise<ExecTelemetry> =>
  apiGet<ExecTelemetry>(`/planner/exec/telemetry?week_start=${weekStart}`);
export const getExecInsights = (weekStart: string): Promise<ExecInsight> =>
  apiPost<ExecInsight>(`/planner/exec/insights?week_start=${weekStart}`);

/* ── Auth hardening (SUMA/WWF) ─────────────────────────────────────────────*/
export const changePassword = (current_password: string, new_password: string): Promise<UserOut> =>
  apiPost<UserOut>("/auth/change-password", { current_password, new_password });
export const provisionUser = (body: {
  username: string; full_name: string; role: string;
  email?: string | null; dept_id?: string | null; cross_department?: boolean;
}): Promise<ProvisionResult> => apiPost<ProvisionResult>("/auth/provision", body);

/* ── Adaptive task tree (P1) ───────────────────────────────────────────────*/
export function getTree(opts: { rootId?: string; departmentId?: string; weekStart?: string } = {}):
  Promise<PlannerTreeNode[]> {
  const q = new URLSearchParams();
  if (opts.rootId) q.set("root_id", opts.rootId);
  if (opts.departmentId) q.set("department_id", opts.departmentId);
  if (opts.weekStart) q.set("week_start", opts.weekStart);
  const qs = q.toString();
  return apiGet<PlannerTreeNode[]>(`/planner/tree${qs ? `?${qs}` : ""}`);
}

/* ── Governance (change-control loop, P2) ──────────────────────────────────*/
export const listProposals = (status?: string): Promise<ChangeProposal[]> =>
  apiGet<ChangeProposal[]>(`/governance/proposals${status ? `?status=${status}` : ""}`);
export const decideProposal = (id: string, decision: "approved" | "rejected", note?: string):
  Promise<ChangeProposal> =>
  apiPost<ChangeProposal>(`/governance/proposals/${id}/decision`, { decision, note: note ?? null });
export const getFieldRegistry = (): Promise<FieldRegistryEntry[]> =>
  apiGet<FieldRegistryEntry[]>("/governance/field-registry");

/* ── AI agent invocation (P2) ──────────────────────────────────────────────*/
export const aiFunctions = (): Promise<AiFunctions> => apiGet<AiFunctions>("/ai/functions");
export const aiInvoke = (functionKey: string, input: string): Promise<AiResult> =>
  apiPost<AiResult>(`/ai/${functionKey}`, { input });

/* ── Self-service password reset (forgot → reset code) ─────────────────────*/
export const resetRequest = (identifier: string): Promise<ResetResult> =>
  apiPost<ResetResult>("/auth/reset-request", { identifier });
export const resetConfirm = (identifier: string, code: string, new_password: string): Promise<UserOut> =>
  apiPost<UserOut>("/auth/reset-confirm", { identifier, code, new_password });

/* ── Admin account lifecycle ───────────────────────────────────────────────*/
export const adminListUsers = (): Promise<AdminUser[]> => apiGet<AdminUser[]>("/auth/users");
export const adminChangeRole = (id: string, role: string): Promise<AdminUser> =>
  apiPatch<AdminUser>(`/auth/users/${id}/role`, { role });
export const adminSetActive = (id: string, active: boolean): Promise<AdminUser> =>
  apiPost<AdminUser>(`/auth/users/${id}/active`, { active });
export const adminResetPassword = (id: string): Promise<ProvisionResult> =>
  apiPost<ProvisionResult>(`/auth/users/${id}/reset-password`);
