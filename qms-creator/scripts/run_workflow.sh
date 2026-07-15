#!/usr/bin/env sh

set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/CONTENT_CREATOR_FRAMEWORK"
FRONTEND_DIR="$ROOT_DIR/qms-ui"

BACKEND_CMD="${BACKEND_CMD:-$ROOT_DIR/.venv/bin/python $BACKEND_DIR/main_api.py}"
FRONTEND_CMD="${FRONTEND_CMD:-npm run dev}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

print_usage() {
  cat <<'USAGE'
Unified run script for the QMS Creator.

Usage:
  ./scripts/run_workflow.sh [mode]

Modes:
  all        Start backend + UI (default)
  backend    Start backend only
  ui         Start UI only
  status     Show quick environment checks

Environment overrides:
  BACKEND_CMD   Command to run backend (default: .venv/bin/python CONTENT_CREATOR_FRAMEWORK/main_api.py)
  FRONTEND_CMD  Command to run UI (default: npm run dev)
  BACKEND_HOST  Host for backend (default: 0.0.0.0)
  BACKEND_PORT  Port for backend (default: 8000)

Examples:
  ./scripts/run_workflow.sh
  BACKEND_CMD="python3 CONTENT_CREATOR_FRAMEWORK/main_api.py" ./scripts/run_workflow.sh backend
USAGE
}

require_dir() {
  if [ ! -d "$1" ]; then
    printf "Missing directory: %s\n" "$1" >&2
    exit 1
  fi
}

check_backend_env() {
  if [ ! -x "$ROOT_DIR/.venv/bin/python" ]; then
    printf "Warning: .venv not found. Backend may fail unless BACKEND_CMD is overridden.\n" >&2
  fi
  if [ ! -f "$BACKEND_DIR/main_api.py" ]; then
    printf "Error: main_api.py not found in %s\n" "$BACKEND_DIR" >&2
    exit 1
  fi
}

check_ui_env() {
  if [ ! -f "$FRONTEND_DIR/package.json" ]; then
    printf "Error: package.json not found in %s\n" "$FRONTEND_DIR" >&2
    exit 1
  fi
}

start_backend() {
  check_backend_env
  printf "Starting backend: %s\n" "$BACKEND_CMD"
  printf "Backend host: %s\n" "$BACKEND_HOST"
  printf "Backend port: %s\n" "$BACKEND_PORT"
  (cd "$ROOT_DIR" && BACKEND_HOST="$BACKEND_HOST" BACKEND_PORT="$BACKEND_PORT" sh -c "$BACKEND_CMD")
}

start_ui() {
  check_ui_env
  printf "Starting UI: %s\n" "$FRONTEND_CMD"
  (cd "$FRONTEND_DIR" && sh -c "$FRONTEND_CMD")
}

show_status() {
  printf "Project root: %s\n" "$ROOT_DIR"
  if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
    printf "Backend venv: OK\n"
  else
    printf "Backend venv: MISSING\n"
  fi

  if [ -f "$FRONTEND_DIR/package.json" ]; then
    printf "UI package.json: OK\n"
  else
    printf "UI package.json: MISSING\n"
  fi

  printf "Backend command: %s\n" "$BACKEND_CMD"
  printf "UI command: %s\n" "$FRONTEND_CMD"
}

main() {
  mode="${1:-all}"

  require_dir "$ROOT_DIR"
  require_dir "$BACKEND_DIR"
  require_dir "$FRONTEND_DIR"

  case "$mode" in
    all)
      start_backend &
      BACKEND_PID=$!
      start_ui &
      UI_PID=$!

      trap 'kill "$BACKEND_PID" "$UI_PID" 2>/dev/null || true' INT TERM
      wait "$BACKEND_PID" "$UI_PID"
      ;;
    backend)
      start_backend
      ;;
    ui)
      start_ui
      ;;
    status)
      show_status
      ;;
    -h|--help|help)
      print_usage
      ;;
    *)
      printf "Unknown mode: %s\n\n" "$mode" >&2
      print_usage
      exit 1
      ;;
  esac
}

main "$@"
