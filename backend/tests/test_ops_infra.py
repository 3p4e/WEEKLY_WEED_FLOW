"""Pins for the operations surface outside the app: the agent's GitHub helper,
the backup scripts, the watchdog, the compose topology, the deploy workflow's
gates and the documents that describe them (review 2026-09-27, round 2:
DI2-05, DI2-06, DI2-08, DI2-11, DI2-12, DI2-14, R2-BC-08, INS2-15, INS2-19,
INV-07). Static and subprocess-level: nothing here reaches a host.
"""
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def _load_gh_api():
    spec = importlib.util.spec_from_file_location("gh_api", ROOT / "ops" / "agent" / "gh_api.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ───────────────────────────── gh_api.py (DI2-08) ─────────────────────────────

@pytest.mark.parametrize("method,path", [
    ("GET", "/repos/3p4e/WEEKLY_WEED_FLOW/%2E%2E/%2E%2E/user"),
    ("GET", "/repos/3p4e/WEEKLY_WEED_FLOW/actions%2Fruns"),
    ("GET", "/repos/3p4e/WEEKLY_WEED_FLOW/x#frag"),
    ("POST", "/repos/3p4e/WEEKLY_WEED_FLOW/actions/workflows/deploy.yml/dispatches%3F"),
    ("GET", "/repos/3p4e/WEEKLY_WEED_FLOW/../../user"),
    ("PUT", "/repos/3p4e/WEEKLY_WEED_FLOW/pulls/52/merge"),
    ("PATCH", "/repos/3p4e/WEEKLY_WEED_FLOW/pulls/52"),
    ("DELETE", "/repos/3p4e/WEEKLY_WEED_FLOW/git/refs/heads/main"),
])
def test_gh_api_refuses_encoded_traversal_and_every_write_off_the_allow_list(method, path):
    ok, why = _load_gh_api().allowed(method, path)
    assert not ok, (method, path)
    assert why


@pytest.mark.parametrize("method,path", [
    ("GET", "/repos/3p4e/WEEKLY_WEED_FLOW/actions/runs?per_page=5"),
    ("POST", "/repos/3p4e/WEEKLY_WEED_FLOW/actions/runs/123/rerun"),
    ("POST", "/repos/3p4e/WEEKLY_WEED_FLOW/actions/workflows/deploy.yml/dispatches"),
    ("POST", "/repos/3p4e/WEEKLY_WEED_FLOW/issues/52/comments"),
])
def test_gh_api_allow_list_still_admits_what_a_session_needs(method, path):
    assert _load_gh_api().allowed(method, path)[0], (method, path)


class _FailingRunner:
    """A kvm4-runner whose /file/write lands the token and whose /shell then
    times out — the exact exit path that used to leave the 0600 token file on
    the host."""

    def __init__(self, shell_exc):
        self.shell_exc = shell_exc
        self.written = []
        self.shells = []

    def file_write(self, remote, content, mode="0600"):
        self.written.append(remote)
        return True

    def shell(self, cmd, timeout=90):
        self.shells.append((cmd, timeout))
        if len(self.shells) == 1:
            raise self.shell_exc
        return {"output": "", "exit_code": 0}


@pytest.mark.parametrize("exc", [
    urllib.error.HTTPError("http://runner/shell", 504, "gateway timeout", {}, None),
    urllib.error.URLError("connection reset"),
    TimeoutError("timed out"),
])
def test_gh_api_shreds_the_staged_token_when_the_shell_call_does_not_come_back(monkeypatch, capsys, exc):
    gh = _load_gh_api()
    runner = _FailingRunner(exc)
    monkeypatch.setattr(gh, "Runner", lambda base, tok: runner)
    monkeypatch.setenv("GITHUB_PAT_WWF", "github_pat_TESTONLYTESTONLYTESTONLY")
    monkeypatch.setenv("RUNNER_URL", "http://runner.invalid")
    monkeypatch.setenv("RUNNER_TOKEN", "runner-token-test")
    rc = gh.main(["GET", "/repos/3p4e/WEEKLY_WEED_FLOW/actions/runners"])
    assert rc == 1
    assert len(runner.written) == 1
    token_file = runner.written[0]
    assert len(runner.shells) == 2, "a second /shell call must remove the staged file"
    cleanup_cmd = runner.shells[1][0]
    assert "shred -u" in cleanup_cmd and token_file in cleanup_cmd
    err = capsys.readouterr().err
    assert "staged token file removed" in err
    assert "github_pat_TESTONLY" not in err and "github_pat_TESTONLY" not in cleanup_cmd


def test_gh_api_cleanup_failure_is_reported_never_hidden(monkeypatch, capsys):
    gh = _load_gh_api()

    class _DeadRunner(_FailingRunner):
        def shell(self, cmd, timeout=90):
            self.shells.append((cmd, timeout))
            raise urllib.error.URLError("still down")
    runner = _DeadRunner(None)
    monkeypatch.setattr(gh, "Runner", lambda base, tok: runner)
    monkeypatch.setenv("GITHUB_PAT_WWF", "ghp_TESTONLYTESTONLYTESTONLY")
    monkeypatch.setenv("RUNNER_URL", "http://runner.invalid")
    monkeypatch.setenv("RUNNER_TOKEN", "runner-token-test")
    assert gh.main(["GET", "/repos/3p4e/WEEKLY_WEED_FLOW/actions/runners"]) == 1
    assert len(runner.shells) == 2
    err = capsys.readouterr().err
    assert "could not remove the staged token file" in err and "rotate GITHUB_PAT_WWF" in err


# ───────────────────── offsite_backup.sh / db_backup.sh (DI2-05) ─────────────────────

def _fake_rclone(tmp_path: Path, copy_rc: int, listing: str) -> Path:
    """An rclone that fails or succeeds `copy` as told, answers `lsf` with the
    given listing, and records every `delete`."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    script = bin_dir / "rclone"
    script.write_text(
        "#!/bin/sh\n"
        f"echo \"$@\" >> {tmp_path / 'rclone.log'}\n"
        "case \"$1\" in\n"
        f"  copy) exit {copy_rc} ;;\n"
        f"  lsf) printf '%s\\n' '{listing}'; exit 0 ;;\n"
        "  delete) exit 0 ;;\n"
        "esac\n"
        "exit 0\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return bin_dir


def _run_offsite_once(tmp_path: Path, copy_rc: int, listing: str, dump_name="wwf_tasks_20260927T030000Z.sql.gz"):
    backups = tmp_path / "backups"
    backups.mkdir(exist_ok=True)
    (backups / dump_name).write_bytes(b"x")
    bin_dir = _fake_rclone(tmp_path, copy_rc, listing)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "BACKUP_DIR": str(backups),
           "RCLONE_REMOTE": "fake:"}
    r = subprocess.run(["sh", str(ROOT / "backend" / "scripts" / "offsite_backup.sh"), "--once"],
                       env=env, capture_output=True, text=True, timeout=60)
    log = (tmp_path / "rclone.log").read_text() if (tmp_path / "rclone.log").exists() else ""
    return r, log


def test_offsite_rotation_never_runs_after_a_failed_copy(tmp_path):
    r, log = _run_offsite_once(tmp_path, copy_rc=1, listing="wwf_tasks_20260927T030000Z.sql.gz")
    assert r.returncode == 1
    assert "delete" not in log, log
    assert "COPY FAILED" in r.stderr and "SKIPPING remote rotation" in r.stderr


def test_offsite_rotation_needs_the_remote_to_list_the_newest_dump(tmp_path):
    r, log = _run_offsite_once(tmp_path, copy_rc=0, listing="wwf_tasks_20260901T030000Z.sql.gz")
    assert r.returncode == 0
    assert "delete" not in log, log
    assert "does not list" in r.stderr


def test_offsite_rotation_runs_when_copy_succeeded_and_the_remote_holds_the_dump(tmp_path):
    r, log = _run_offsite_once(tmp_path, copy_rc=0, listing="wwf_tasks_20260927T030000Z.sql.gz")
    assert r.returncode == 0, r.stderr
    assert "delete fake: --min-age 60d" in log, log


def test_offsite_rotation_pauses_while_no_fresh_local_dump_exists(tmp_path):
    backups = tmp_path / "backups"
    backups.mkdir()
    old = backups / "wwf_tasks_20260101T030000Z.sql.gz"
    old.write_bytes(b"x")
    os.utime(old, (0, 0))
    bin_dir = _fake_rclone(tmp_path, 0, old.name)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "BACKUP_DIR": str(backups),
           "RCLONE_REMOTE": "fake:"}
    r = subprocess.run(["sh", str(ROOT / "backend" / "scripts" / "offsite_backup.sh"), "--once"],
                       env=env, capture_output=True, text=True, timeout=60)
    assert "delete" not in (tmp_path / "rclone.log").read_text()
    assert "db-backup is not producing" in r.stderr


def test_db_backup_fails_the_cycle_when_a_known_docengine_mount_is_gone():
    src = (ROOT / "backend" / "scripts" / "db_backup.sh").read_text()
    branch = src.split("elif ls \"$BACKUP_DIR\"/docengine_out_*.tar.gz", 1)
    assert len(branch) == 2, "the lost-mount branch must key on an existing archive"
    assert "ok=0" in branch[1].split("else", 1)[0]
    assert subprocess.run(["sh", "-n", str(ROOT / "backend" / "scripts" / "db_backup.sh")]).returncode == 0


def test_watchdog_fails_when_docengine_runs_and_no_archive_exists():
    src = (ROOT / "ops" / "watchdog.sh").read_text()
    # the verdict arm (after `case "$name" in`), not the glob arm inside the
    # container snippet that also reads `docengine_out)`
    arm = src.split('case "$name" in', 1)[1].split("docengine_out)", 1)[1].split(";;", 1)[0]
    assert "worst=FAIL" in arm and "DOCENGINE_CONTAINER" in arm and "= running" in arm
    assert subprocess.run(["bash", "-n", str(ROOT / "ops" / "watchdog.sh")]).returncode == 0


# ───────────────────────── compose topology (DI2-14) ─────────────────────────

def test_capture_connector_reaches_the_backend_only():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    svc, nets = compose["services"], compose["networks"]
    assert nets["capture"]["internal"] is True
    assert "internal" not in svc["capture-mcp"]["networks"]
    assert set(svc["capture-mcp"]["networks"]) == {"capture", "traefik"}
    assert "capture" in svc["backend"]["networks"]
    for name in ("db-users", "db-tasks", "docengine", "scheduler", "db-backup", "backup-offsite"):
        assert "capture" not in svc[name].get("networks", []), name
    assert "capture" not in svc["frontend"]["networks"]


# ───────────────────────── deploy.yml gates (DI2-06, DI2-11) ─────────────────────────

def _deploy_yml() -> str:
    return (ROOT / ".github" / "workflows" / "deploy.yml").read_text()


def test_every_workflow_parses():
    for f in (ROOT / ".github" / "workflows").glob("*.yml"):
        assert yaml.safe_load(f.read_text()), f


def test_deploy_preflight_requires_docengine_only_in_its_own_scope():
    src = _deploy_yml()
    preflight = src.split("phase_preflight() {", 1)[1].split("phase_build() {", 1)[0] \
        if "phase_build() {" in src else src.split("phase_preflight() {", 1)[1]
    assert 'required_cts="$BACKEND_CT $SCHEDULER_CT $FRONTEND_CT $USERS_DB_CT $TASKS_DB_CT"' in preflight
    assert 'if [ "$DO_DOCENGINE" = true ]; then required_cts="$required_cts $DOCENGINE_CT"; fi' in preflight
    assert 'svc_pairs+=("DOCENGINE_SVC $DOCENGINE_CT")' in preflight
    assert '"DOCENGINE_SVC $DOCENGINE_CT" \\' not in preflight, "unconditional DocEngine service derivation"


def test_deploy_gate_compares_the_ci_entry_points_and_says_what_it_cannot_prove():
    src = _deploy_yml()
    for path in ("backend/scripts/load_schema.sh", "backend/requirements.txt",
                 "backend/requirements-dev.txt", "docengine/requirements.txt",
                 "docengine/sql/docengine_role.sql", "connector/requirements.txt",
                 "tests/frontend/package.json", "tests/frontend/package-lock.json",
                 "web/e2e/package.json", "web/e2e/package-lock.json",
                 "web/e2e/playwright.config.js"):
        assert f'"{path}"' in src, path
        assert (ROOT / path).exists(), f"{path} named by the gate does not exist"
    assert "The code under test is still the branch's own" in src


def test_deploy_script_heredoc_passes_bash_n():
    src = _deploy_yml()
    body = src.split("<<'DEPLOY_SH'\n", 1)[1].split("\n          DEPLOY_SH\n", 1)[0]
    lines = [ln[10:] if ln.startswith("          ") else ln for ln in body.splitlines()]
    r = subprocess.run(["bash", "-n"], input="\n".join(lines) + "\n", capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ───────────────────────────── documents ─────────────────────────────

def test_deploy_md_describes_the_real_deploy_path_and_the_rollout_steps():
    doc = (ROOT / "docs" / "DEPLOY.md").read_text()
    assert "KVM4_SSH_KEY" not in doc and "rsyncs the repo" not in doc, "the SSH/rsync story is fiction"
    assert "kvm4-runner `/shell` API" in doc
    for heading in ("### Client address trust", "### Capture connector network",
                    "### Password policy floor", "### Registry identity"):
        assert heading in doc, heading
    assert "PASSWORD_POLICY_OVERRIDE=true" in doc
    assert "TRAEFIK_HOST" in doc
    # the DocEngine section no longer says it runs on the decommissioned test
    # stack (other dated historical sections keep their wording on purpose)
    de = doc.split("## GrowFlow DocEngine", 1)[1].split("\n## ", 1)[0]
    assert "Deployed to **wwf_mass (test) only**" not in de
    assert "historical (written 2026-07-19)" in de
    assert "(qcm.blani)" not in doc
    assert "networks: [internal, ainet]" in doc
    env = (ROOT / ".env.example").read_text()
    assert "PASSWORD_POLICY_OVERRIDE" in env and "2026-09-04" in env


def test_claude_md_describes_the_helper_allow_list_and_the_working_file_write():
    doc = (ROOT / "CLAUDE.md").read_text()
    assert "gh_api.py GET|POST /repos" in doc
    assert "GET|POST|PUT|PATCH" not in doc
    assert "It refuses DELETE and any path outside this repo" not in doc
    assert "allow-list" in doc and "deploy.yml included" in doc
    assert "endpoint is **not needed**" not in doc
    assert "`/file/write` works" in doc


def test_engine_guide_no_longer_describes_the_removed_suite_as_present():
    guide = (ROOT / "docengine" / "engine" / "references" / "GUIDE_bilingual_markdown.md").read_text()
    assert "is a frozen preservation snapshot" not in guide
    assert "Both trees are frozen" not in guide
    assert "no longer exists" in guide
    assert not (ROOT / "docengine" / "pp-document-suite").exists()
    build = (ROOT / "docengine" / "engine" / "scripts" / "build_from_md.py").read_text()
    assert "pp-document-suite\", \"scripts\"" not in build


def test_frontend_realip_hook_is_executable_in_git():
    hook = ROOT / "web" / "docker-entrypoint.d" / "05-wwf-realip.sh"
    assert hook.exists()
    assert subprocess.run(["sh", "-n", str(hook)]).returncode == 0
    if shutil.which("git"):
        mode = subprocess.run(["git", "ls-files", "-s", str(hook)], cwd=ROOT,
                              capture_output=True, text=True).stdout.split()
        assert mode and mode[0] == "100755", "the hook must be committed executable or the image ignores it"
