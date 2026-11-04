"""Configure optional publishing without putting credentials in command arguments or chat.

Default: create/adopt a Direct Upload Pages project and set encrypted GitHub
production-environment secrets. --check is read-only and used by GitHub Actions.
--publisher-token stores a separately scoped GitHub token in ignored local .env.
None of these modes deploys a book or enables publication.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "Tetsuya-Uchimura/memoryweaver-stories"
DEFAULT_PROJECT = "memoryweaver-stories"


class SetupError(Exception):
    pass


def request_json(method, url, token, payload=None, allow_missing=False):
    request = urllib.request.Request(url, method=method, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "MemoryWeaver-Publishing-Setup"}, data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and allow_missing:
            return None
        # Do not echo response bodies or request objects: either can hold credentials.
        raise SetupError(f"{method} failed (HTTP {exc.code}). Check account, resource name, and token permissions.") from None
    except (urllib.error.URLError, TimeoutError):
        raise SetupError("Could not reach the provider; check your network and retry.") from None


def pages_project(account, project, token, create=False):
    if not re.fullmatch(r"[a-fA-F0-9]{32}", account):
        raise SetupError("Cloudflare Account ID must contain 32 hexadecimal characters.")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,56}[a-z0-9])?", project):
        raise SetupError("Use a Pages project name of 1–58 lowercase letters, numbers, or hyphens.")
    if not token or any(c.isspace() for c in token):
        raise SetupError("A nonempty Cloudflare API token without whitespace is required.")
    base = f"https://api.cloudflare.com/client/v4/accounts/{account}/pages/projects"
    result = request_json("GET", base + "/" + project, token, allow_missing=create)
    if result is None:
        result = request_json("POST", base, token, {"name": project, "production_branch": "main"})
    if not result.get("success") or not isinstance(result.get("result"), dict):
        raise SetupError("Cloudflare did not return a valid Pages project. Check the token and account.")
    value = result["result"]
    if value.get("source"):
        raise SetupError("This project uses Git integration. Select a Direct Upload project to preserve the approval-controlled deployment path.")
    if value.get("production_branch") != "main" or value.get("name") != project:
        raise SetupError("Expected the selected Pages project with production branch main; existing settings were left unchanged.")
    return value


def gh(*args, secret=None):
    result = subprocess.run(["gh", *args], input=secret, text=True, capture_output=True)
    if result.returncode:
        raise SetupError("GitHub CLI operation failed. Run gh auth status and check repository admin/workflow access. Credential-bearing output was withheld.")
    return result.stdout


def require_private_repo(repo):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise SetupError("Repository must be owner/name.")
    metadata = json.loads(gh("repo", "view", repo, "--json", "isPrivate,defaultBranchRef,viewerPermission"))
    if not metadata["isPrivate"]:
        raise SetupError("A private repository is required for publication.")
    if metadata["defaultBranchRef"]["name"] != "main":
        raise SetupError("Initialize the repository with a main branch before configuring publication.")


def update_local_env(repo, token):
    path = ROOT / ".env"
    if not path.is_file():
        raise SetupError("Run python3 scripts/dev.py prepare before configuring the local Publisher.")
    lines = path.read_text().splitlines()
    values = {"PUBLISH_GITHUB_REPOSITORY": repo, "PUBLISH_GITHUB_BRANCH": "main", "PUBLISH_GITHUB_TOKEN": token, "PUBLISH_ENABLED": "false"}
    updated = []
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line and not line.startswith("#") else None
        if key in values:
            updated.append(key + "=" + values.pop(key))
        else:
            updated.append(line)
    updated.extend(key + "=" + value for key, value in values.items())
    # Atomic owner-readable replacement; credentials never enter shell args or logs.
    fd, filename = tempfile.mkstemp(prefix=".mw-setup-", dir=ROOT)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write("\n".join(updated) + "\n")
        os.replace(filename, path)
    finally:
        if Path(filename).exists():
            Path(filename).unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--project", default=os.getenv("CLOUDFLARE_PAGES_PROJECT", DEFAULT_PROJECT))
    parser.add_argument("--account-id", default=os.getenv("CLOUDFLARE_ACCOUNT_ID"))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true", help="Read-only credential and project check; no prompts")
    modes.add_argument("--publisher-token", action="store_true", help="Configure the local Publisher's separately scoped GitHub token")
    args = parser.parse_args()
    if args.check:
        token = os.getenv("CLOUDFLARE_API_TOKEN", "")
        if not args.account_id or not token:
            raise SetupError("Set production-environment secrets CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN first.")
        pages_project(args.account_id, args.project, token)
        print("PASS: Cloudflare credentials can read the Direct Upload project; production branch is main. No book was deployed.")
        return
    if not sys.stdin.isatty():
        raise SetupError("Run this interactive setup in your own terminal. Do not send tokens through chat or command-line flags.")
    require_private_repo(args.repo)
    if args.publisher_token:
        token = getpass.getpass("Fine-grained GitHub token (Contents write + Commit statuses read; hidden): ").strip()
        if not token or not re.fullmatch(r"[A-Za-z0-9_]+", token):
            raise SetupError("Invalid GitHub token format.")
        metadata = request_json("GET", "https://api.github.com/repos/" + args.repo, token)
        if metadata.get("full_name", "").lower() != args.repo.lower() or not metadata.get("private"):
            raise SetupError("This token cannot read the selected private repository.")
        update_local_env(args.repo, token)
        print("Publisher token saved to ignored .env with owner-only permissions. Repository read access verified; Contents write remains required. PUBLISH_ENABLED=false.")
        return
    account = args.account_id or input("Cloudflare Account ID: ").strip()
    token = getpass.getpass("Cloudflare API token (Account / Cloudflare Pages / Edit; hidden): ").strip()
    pages_project(account, args.project, token, create=True)
    gh("api", "--method", "PUT", f"repos/{args.repo}/environments/production")
    gh("secret", "set", "CLOUDFLARE_API_TOKEN", "--repo", args.repo, "--env", "production", secret=token)
    gh("secret", "set", "CLOUDFLARE_ACCOUNT_ID", "--repo", args.repo, "--env", "production", secret=account)
    gh("variable", "set", "CLOUDFLARE_PAGES_PROJECT", "--repo", args.repo, "--env", "production", "--body", args.project)
    gh("workflow", "run", "publishing-readiness.yml", "--repo", args.repo, "--ref", "main")
    print("Cloudflare Direct Upload project and encrypted GitHub production settings are ready.")
    print(f"Read-only readiness check started: https://github.com/{args.repo}/actions/workflows/publishing-readiness.yml")
    print("No travel book was deployed. Cloudflare token was not written to disk. Local publishing remains disabled.")


if __name__ == "__main__":
    try:
        main()
    except (SetupError, FileNotFoundError) as exc:
        raise SystemExit(str(exc))
    except (KeyboardInterrupt, EOFError):
        raise SystemExit("Setup stopped; no book was deployed.")
