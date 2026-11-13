"""Controles de aislamiento de los procesos que ejecutan código generado o legacy."""
from __future__ import annotations

import json
import os
import sys

from copilot.engine.sandbox import run_cmd


def test_isolated_process_has_minimal_environment_and_no_root(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTCS_TEST_PRIVATE_SECRET", "must-not-leak")
    script = ("import json, os; print(json.dumps({"
              "'secret': os.environ.get('AGENTCS_TEST_PRIVATE_SECRET'), "
              "'home': os.environ.get('HOME'), "
              "'uid': os.geteuid() if hasattr(os, 'geteuid') else None}))")
    result = run_cmd([sys.executable, "-c", script], tmp_path, isolated=True)

    assert result.ok, result.tail()
    observed = json.loads(result.stdout)
    assert observed["secret"] is None
    assert observed["home"] == str(tmp_path.resolve())
    if os.name == "posix" and os.geteuid() == 0:
        assert observed["uid"] == int(os.environ.get("AGENTCS_SANDBOX_UID", "10001"))
