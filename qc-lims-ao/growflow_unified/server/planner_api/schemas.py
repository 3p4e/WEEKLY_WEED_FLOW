"""Pydantic v2 contracts for the Planner API (cross-boundary shapes for the web app)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class Health(BaseModel):
    status: str = "ok"
    service: str
    version: str


# --- Auth ------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str                       # username or email
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    full_name: str
    role: str                           # operator|hod|qa|qp|executive|admin
    email: str | None = None
    avatar_url: str | None = None
    dept_id: str | None = None
    dept_key: str | None = None
    must_change_password: bool = False
    cross_department: bool = False


class ProvisionRequest(BaseModel):
    username: str
    full_name: str
    role: str                           # operator|qa|qp|hod|executive|admin
    email: str | None = None
    dept_id: str | None = None
    cross_department: bool = False      # inter-department (team-leader / coordinator)


class ProvisionResult(BaseModel):
    id: str
    username: str
    role: str
    temp_password: str                  # the OTP — shown ONCE
    expires_hours: int


class ResetRequest(BaseModel):
    identifier: str                     # username or email


class ResetConfirm(BaseModel):
    identifier: str
    code: str
    new_password: str


class ResetResult(BaseModel):
    sent: bool = True
    delivery: str = "email"             # email | shown (no provider configured)
    code: str | None = None             # only when delivery == 'shown'


class RoleChange(BaseModel):
    role: str


class ActiveChange(BaseModel):
    active: bool


class AdminUserOut(BaseModel):
    id: str
    username: str
    full_name: str
    role: str
    email: str | None = None
    dept_id: str | None = None
    dept_key: str | None = None
    is_active: bool = True
    cross_department: bool = False
    must_change_password: bool = False
    last_login_at: datetime | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --- Departments + tasks ---------------------------------------------------
class PlannerDepartment(BaseModel):
    id: str
    key: str
    name_en: str
    name_mk: str
    icon: str | None = None
    color: str | None = None
    handoff_to_id: str | None = None
    position: int = 0


class PlannerSubtask(BaseModel):
    id: str | None = None
    text: str
    done: bool = False
    position: int = 0


class PlannerProgressNote(BaseModel):
    id: str
    day: str | None = None
    note: str
    author_id: str | None = None
    author_name: str | None = None
    created_at: datetime | None = None


class PlannerHandoff(BaseModel):
    id: str
    to_department_id: str
    to_department_key: str | None = None
    status: str = "requested"           # requested|accepted|done
    requested_by: str | None = None
    created_at: datetime | None = None


class PlannerTask(BaseModel):
    id: str
    department_id: str
    department_key: str | None = None
    title: str
    owner_id: str | None = None
    owner_name: str | None = None
    status: str = "pending"             # pending|working|review|stuck|postponed|done
    priority: str = "medium"           # critical|high|medium|low
    week_start: date
    days: list[str] = []                # Mon..Sun
    room: str | None = None
    batch: str | None = None
    tags: list[str] = []
    description: str | None = None
    blocker: str | None = None
    outcome: str | None = None          # solution / resolution narrative (QC lifecycle)
    # Assignment acknowledgment (assignee accepts or declines the work).
    assignment_status: str = "accepted"  # pending|accepted|declined
    assignment_responded_at: datetime | None = None
    assignment_note: str | None = None
    position: int = 0
    # Adaptive tree (P1): a node is a task | annex | step; depth varies by need.
    parent_id: str | None = None
    node_kind: str = "task"             # task | annex | step
    is_sop: bool = False
    annex_count: int = 0
    attributes: dict = {}               # extensible long-tail params (JSONB)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    child_count: int = 0
    helper_ids: list[str] = []
    subtasks: list[PlannerSubtask] = []
    notes: list[PlannerProgressNote] = []
    deps: list[str] = []                # task ids this task depends on
    handoffs: list[PlannerHandoff] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None


class PlannerTreeNode(BaseModel):
    """A node in the adaptive task tree (recursive children)."""
    id: str
    parent_id: str | None = None
    title: str
    node_kind: str = "task"
    status: str = "pending"
    priority: str = "medium"
    is_sop: bool = False
    annex_count: int = 0
    owner_name: str | None = None
    department_key: str | None = None
    attributes: dict = {}
    started_at: datetime | None = None
    ended_at: datetime | None = None
    children: list["PlannerTreeNode"] = []


class PlannerTaskCreate(BaseModel):
    department_id: str
    title: str
    week_start: date
    owner_id: str | None = None
    status: str = "pending"
    priority: str = "medium"
    days: list[str] = []
    room: str | None = None
    batch: str | None = None
    tags: list[str] = []
    description: str | None = None
    blocker: str | None = None
    outcome: str | None = None
    parent_id: str | None = None
    node_kind: str = "task"
    is_sop: bool = False
    attributes: dict = {}
    helper_ids: list[str] = []
    subtasks: list[PlannerSubtask] = []
    deps: list[str] = []


class PlannerTaskUpdate(BaseModel):
    department_id: str | None = None
    title: str | None = None
    owner_id: str | None = None
    status: str | None = None
    priority: str | None = None
    week_start: date | None = None
    days: list[str] | None = None
    room: str | None = None
    batch: str | None = None
    tags: list[str] | None = None
    description: str | None = None
    blocker: str | None = None
    outcome: str | None = None
    position: int | None = None
    parent_id: str | None = None
    node_kind: str | None = None
    is_sop: bool | None = None
    attributes: dict | None = None
    helper_ids: list[str] | None = None
    subtasks: list[PlannerSubtask] | None = None
    deps: list[str] | None = None


class PlannerNoteCreate(BaseModel):
    note: str
    day: str | None = None


class PlannerHandoffCreate(BaseModel):
    to_department_id: str


class AssignmentDecision(BaseModel):
    decision: str                       # accepted | declined
    note: str | None = None             # optional reason (esp. on decline)


class PlannerTelemetry(BaseModel):
    week_start: date
    total: int = 0
    completion: int = 0                 # percent done
    by_status: dict[str, int] = {}      # status -> count
    busiest_day: str | None = None


# --- Weekly reports + AI ---------------------------------------------------
class PlannerWeeklyReport(BaseModel):
    id: str
    user_id: str
    user_name: str | None = None
    week_start: date
    completed_summary: str | None = None
    progress_summary: str | None = None
    next_week_plan: str | None = None
    status: str = "draft"               # draft|submitted
    ai_generated: bool = False
    submitted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PlannerWeeklyReportUpdate(BaseModel):
    completed_summary: str | None = None
    progress_summary: str | None = None
    next_week_plan: str | None = None


class AiDraftResult(BaseModel):
    """AI-drafted report sections. available=False ⇒ gateway unconfigured/unreachable."""
    available: bool = True
    completed_summary: str | None = None
    progress_summary: str | None = None
    next_week_plan: str | None = None
    note: str | None = None


class RewriteRequest(BaseModel):
    text: str
    tone: str = "concise"               # concise|formal|friendly


class RewriteResult(BaseModel):
    available: bool = True
    text: str
    note: str | None = None


class RolloverResult(BaseModel):
    created: int = 0
    target_week: date


# --- Executive analytics ---------------------------------------------------
class ExecDeptStat(BaseModel):
    dept_id: str
    dept_key: str
    name_en: str
    name_mk: str
    total: int = 0
    done: int = 0
    stuck: int = 0
    completion: int = 0


class ExecUserStat(BaseModel):
    user_id: str
    user_name: str
    dept_key: str | None = None
    total: int = 0
    done: int = 0
    completion: int = 0


class ExecTelemetry(BaseModel):
    week_start: date
    total: int = 0
    completion: int = 0
    by_status: dict[str, int] = {}
    busiest_day: str | None = None
    headcount: int = 0
    reports_submitted: int = 0
    by_department: list[ExecDeptStat] = []
    by_user: list[ExecUserStat] = []


class ExecInsight(BaseModel):
    """AI executive analysis over all users' weekly reports + telemetry.
    available=False ⇒ gateway unconfigured/unreachable (graceful degradation)."""
    available: bool = True
    summary: str | None = None
    highlights: list[str] = []
    risks: list[str] = []
    foresight: str | None = None
    sources: list[str] = []
    note: str | None = None


# --- Governance (change-control loop, P2) ----------------------------------
class ChangeProposalOut(BaseModel):
    id: str
    proposed_by: str
    kind: str                           # add_field|promote_field|add_dependency|add_subworkflow
    target: str | None = None
    payload: dict = {}
    rationale: str
    evidence: dict = {}
    status: str = "pending"             # pending|approved|rejected|applied
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime | None = None


class ProposalDecision(BaseModel):
    decision: str                       # approved | rejected
    note: str | None = None


class FieldRegistryOut(BaseModel):
    key: str
    label_en: str
    label_mk: str | None = None
    data_type: str = "text"
    applies_to: str = "task"
    status: str = "active"
    promoted: bool = False


# --- AI invocation (data-driven bindings, P2) ------------------------------
class AiFunctionsOut(BaseModel):
    catalog: dict[str, str] = {}
    active: list[str] = []


class AiInvokeRequest(BaseModel):
    input: str
    context: dict | None = None


class AiInvokeResult(BaseModel):
    available: bool = True
    function: str | None = None
    output: str | None = None
    reason: str | None = None


# Resolve the self-referencing PlannerTreeNode.children forward reference.
PlannerTreeNode.model_rebuild()
