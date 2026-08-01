import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "module",
    ["scripts.run_email_worker", "scripts.run_telegram_bot"],
)
def test_worker_module_entrypoint_loads_application_package(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
