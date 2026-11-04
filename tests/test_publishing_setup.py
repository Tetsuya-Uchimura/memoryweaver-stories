import json
import os
from pathlib import Path
import stat
import subprocess

import pytest
from scripts import setup_publishing as setup


def test_new_direct_upload_project_uses_documented_api(monkeypatch):
    calls = []
    def request(method, url, token, payload=None, allow_missing=False):
        calls.append((method, url, payload, allow_missing))
        if method == "GET":
            return None
        return {"success": True, "result": {"name": "memoryweaver-stories", "production_branch": "main"}}
    monkeypatch.setattr(setup, "request_json", request)
    setup.pages_project("a" * 32, "memoryweaver-stories", "hidden-test-token", create=True)
    assert calls == [
        ("GET", "https://api.cloudflare.com/client/v4/accounts/" + "a" * 32 + "/pages/projects/memoryweaver-stories", None, True),
        ("POST", "https://api.cloudflare.com/client/v4/accounts/" + "a" * 32 + "/pages/projects", {"name": "memoryweaver-stories", "production_branch": "main"}, False),
    ]


@pytest.mark.parametrize("project", [
    {"name": "memoryweaver-stories", "production_branch": "main", "source": {"type": "github"}},
    {"name": "memoryweaver-stories", "production_branch": "another-branch"},
])
def test_existing_project_is_not_reconfigured_or_deployed(monkeypatch, project):
    calls = []
    def request(method, *args, **kwargs):
        calls.append(method)
        return {"success": True, "result": project}
    monkeypatch.setattr(setup, "request_json", request)
    with pytest.raises(setup.SetupError):
        setup.pages_project("a" * 32, "memoryweaver-stories", "hidden-test-token", create=True)
    assert calls == ["GET"]


def test_local_token_setup_preserves_settings_and_disables_publication(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    path = tmp_path / ".env"
    path.write_text("AI_MODE=live\nPUBLISH_ENABLED=true\nWEB_INTERNAL_TOKEN=keep-private\n")
    setup.update_local_env("example/private-repo", "github_pat_test_fixture")
    values = dict(line.split("=", 1) for line in path.read_text().splitlines())
    assert values["PUBLISH_ENABLED"] == "false"
    assert values["AI_MODE"] == "live"
    assert values["WEB_INTERNAL_TOKEN"] == "keep-private"
    assert values["PUBLISH_GITHUB_REPOSITORY"] == "example/private-repo"
    assert values["PUBLISH_GITHUB_TOKEN"] == "github_pat_test_fixture"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".mw-setup-*"))


def test_gh_secrets_pass_through_stdin_and_errors_are_redacted(monkeypatch):
    observed = {}
    def run(command, **kwargs):
        observed.update(command=command, **kwargs)
        return subprocess.CompletedProcess(command, 1, "credential-bearing output", "credential-bearing error")
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(setup.SetupError) as error:
        setup.gh("secret", "set", "CLOUDFLARE_API_TOKEN", secret="sensitive-test-token")
    assert "sensitive-test-token" not in observed["command"]
    assert observed["input"] == "sensitive-test-token"
    assert "credential-bearing" not in str(error.value)
