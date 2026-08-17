# docengine.app.config — environment-driven settings (no pydantic dependency:
# this service stays lean; every knob is a 12-factor env var).
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # docengine/
ENGINE_SCRIPTS = ROOT / "engine" / "scripts"
ENGINE_ASSETS = ROOT / "engine" / "assets"


class Settings:
    # Auth: the WWF backend proxy injects this header server-side (same
    # pattern as qms-api). Empty key = service refuses to start in prod mode.
    api_key: str = os.environ.get("DOCENGINE_API_KEY", "")

    # Letta (direct REST — the Rust MCP bridge has a known decode bug).
    letta_base: str = os.environ.get("LETTA_BASE_URL", "").rstrip("/")
    letta_key: str = os.environ.get("LETTA_API_KEY", "")
    # A stateful-agent generation can take minutes; the read timeout must cover
    # ONE agent turn (the pipeline makes ~11 sequential calls, each polled as a
    # background job). Connect stays short so an unreachable server fails fast.
    letta_read_timeout: float = float(os.environ.get("LETTA_READ_TIMEOUT", "300"))
    letta_connect_timeout: float = float(os.environ.get("LETTA_CONNECT_TIMEOUT", "15"))

    # Postgres for workflow state (fixes the per-worker in-memory bug class).
    # e.g. postgresql://docengine:...@wwf-tasks-db:5432/wwf_tasks
    database_url: str = os.environ.get("DOCENGINE_DATABASE_URL", "")

    # Where produced .docx artifacts live (volume-mounted in the stack).
    out_dir: Path = Path(os.environ.get("DOCENGINE_OUT_DIR", "/data/docengine-out"))

    # Gotenberg for DOCX→PDF (already in the kvm4 letta stack).
    gotenberg_url: str = os.environ.get("GOTENBERG_URL", "").rstrip("/")

    # RAGflow is the single RAG for the whole stack — Letta keeps no sources of
    # its own. These are injected as tool_exec_environment_variables on each
    # gf_ agent so the ragflow_search tool can authenticate from its sandbox.
    # Which datasets each agent may search is declared in agents/fleet.yaml,
    # not here (one source of truth, versioned with the personas).
    ragflow_base: str = os.environ.get("RAGFLOW_BASE_URL", "").rstrip("/")
    ragflow_key: str = os.environ.get("RAGFLOW_API_KEY", "")


settings = Settings()
