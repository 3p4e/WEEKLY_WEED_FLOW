-- ============================================================================
-- Planner — standalone schema (PostgreSQL 16 + pgvector)
-- Canonical DDL; the Alembic 0001 baseline executes this file verbatim.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;      -- pgvector (report embeddings)
CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- gen_random_uuid(), gen_salt('bf')

-- ---------------------------------------------------------------------------
-- Departments (GrowFlow-flavored, bilingual EN/MK)
-- ---------------------------------------------------------------------------
CREATE TABLE planner_department (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key             TEXT NOT NULL UNIQUE,
    name_en         TEXT NOT NULL,
    name_mk         TEXT NOT NULL,
    icon            TEXT,
    color           TEXT,
    handoff_to_id   UUID REFERENCES planner_department(id),  -- next dept in the chain
    position        INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Users (JWT auth; bcrypt password hash)
-- ---------------------------------------------------------------------------
CREATE TABLE app_user (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        TEXT NOT NULL UNIQUE,
    full_name       TEXT NOT NULL,
    role            TEXT NOT NULL,            -- operator | hod | qa | qp | executive | admin
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    password_hash   TEXT,                     -- bcrypt ($2*); NULL = cannot log in
    email           TEXT UNIQUE,
    avatar_url      TEXT,
    dept_id         UUID REFERENCES planner_department(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Tasks + children
-- ---------------------------------------------------------------------------
CREATE TABLE planner_task (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    department_id   UUID NOT NULL REFERENCES planner_department(id),
    title           TEXT NOT NULL,
    owner_id        UUID REFERENCES app_user(id),
    status          TEXT NOT NULL DEFAULT 'pending',   -- pending|working|review|stuck|postponed|done
    priority        TEXT NOT NULL DEFAULT 'medium',    -- critical|high|medium|low
    week_start      DATE NOT NULL,                      -- the Monday of the task's week
    days            TEXT[] NOT NULL DEFAULT '{}',       -- Mon..Sun
    room            TEXT,
    batch           TEXT,
    tags            TEXT[] NOT NULL DEFAULT '{}',
    description     TEXT,
    blocker         TEXT,                               -- set when status='stuck'
    created_by      UUID REFERENCES app_user(id),
    position        INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ                          -- set when status -> done
);
CREATE INDEX idx_planner_task_dept   ON planner_task(department_id);
CREATE INDEX idx_planner_task_owner  ON planner_task(owner_id);
CREATE INDEX idx_planner_task_week   ON planner_task(week_start);
CREATE INDEX idx_planner_task_status ON planner_task(status);

CREATE TABLE planner_task_helper (
    task_id         UUID NOT NULL REFERENCES planner_task(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES app_user(id),
    PRIMARY KEY (task_id, user_id)
);

CREATE TABLE planner_subtask (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID NOT NULL REFERENCES planner_task(id) ON DELETE CASCADE,
    text            TEXT NOT NULL,
    done            BOOLEAN NOT NULL DEFAULT FALSE,
    position        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_planner_subtask_task ON planner_subtask(task_id);

CREATE TABLE planner_progress_note (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID NOT NULL REFERENCES planner_task(id) ON DELETE CASCADE,
    day             TEXT,                               -- Mon..Sun (optional)
    note            TEXT NOT NULL,
    author_id       UUID REFERENCES app_user(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_planner_note_task ON planner_progress_note(task_id);

CREATE TABLE planner_task_dependency (
    task_id            UUID NOT NULL REFERENCES planner_task(id) ON DELETE CASCADE,
    depends_on_task_id UUID NOT NULL REFERENCES planner_task(id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, depends_on_task_id)
);

CREATE TABLE planner_handoff (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id            UUID NOT NULL REFERENCES planner_task(id) ON DELETE CASCADE,
    to_department_id   UUID NOT NULL REFERENCES planner_department(id),
    status             TEXT NOT NULL DEFAULT 'requested',  -- requested|accepted|done
    requested_by       UUID REFERENCES app_user(id),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_planner_handoff_task ON planner_handoff(task_id);

-- ---------------------------------------------------------------------------
-- Weekly reports (one per user per week) + embeddings (executive RAG)
-- ---------------------------------------------------------------------------
CREATE TABLE planner_weekly_report (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES app_user(id),
    week_start        DATE NOT NULL,
    completed_summary TEXT,
    progress_summary  TEXT,
    next_week_plan    TEXT,
    status            TEXT NOT NULL DEFAULT 'draft',   -- draft|submitted
    ai_generated      BOOLEAN NOT NULL DEFAULT FALSE,
    submitted_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, week_start)
);
CREATE INDEX idx_planner_report_week ON planner_weekly_report(week_start);

CREATE TABLE planner_report_embedding (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id   UUID NOT NULL REFERENCES planner_weekly_report(id) ON DELETE CASCADE,
    chunk_text  TEXT NOT NULL,
    embedding   vector(1536),                           -- text-embedding-3-small
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_planner_report_embed ON planner_report_embedding
    USING hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- Audit trail (append-only, hash-chained)
-- ---------------------------------------------------------------------------
CREATE TABLE audit_event (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id        UUID REFERENCES app_user(id),
    action          TEXT NOT NULL,               -- submit|ai_draft|ai_rewrite|ai_exec_insights
    entity_type     TEXT NOT NULL,
    entity_id       UUID,
    payload         JSONB NOT NULL,
    prev_hash       BYTEA,
    payload_hash    BYTEA NOT NULL,              -- sha256(prev_hash || canonical_json(payload))
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_entity ON audit_event(entity_type, entity_id);
CREATE INDEX idx_audit_time   ON audit_event(occurred_at);
