from pathlib import Path
import os
import subprocess
import sys


PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / "scripts" / "configure_mysql_permissions.py"
EXPECTED = [
    "PRECHECK root connectivity",
    "PRECHECK 15 stt tables",
    "PRECHECK stt_app connectivity",
    "REVOKE CREATE, DROP, ALTER, INDEX ON stock_data.* FROM stt_app@%",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON stock_data.* TO stt_app@%",
]


def run_script(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["MYSQL_ROOT_PASSWORD"] = "unit-test-secret-that-must-not-print"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=PROJECT.parent,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_permission_script_defaults_to_a_non_connecting_dry_run() -> None:
    result = run_script()

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == EXPECTED
    assert result.stderr == ""


def test_explicit_dry_run_never_prints_passwords() -> None:
    result = run_script("--dry-run")
    combined = result.stdout + result.stderr

    assert result.returncode == 0
    assert result.stdout.splitlines() == EXPECTED
    assert "unit-test-secret-that-must-not-print" not in combined
    assert "mysql+pymysql://" not in combined


def test_permission_modes_are_mutually_exclusive() -> None:
    result = run_script("--dry-run", "--apply")

    assert result.returncode == 2
    assert "configuration FAILED" not in result.stdout
