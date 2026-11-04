#!/usr/bin/env python3
"""Portable, idempotent launcher. No developer credentials are needed."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SWITCH_COMMIT = "6e4ade5269d65ee38060a9f43b77c5e5b3be2f10"
SOURCE = ROOT / ".runtime/switch"


def run(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def prepare():
    if not SOURCE.exists():
        SOURCE.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "init", str(SOURCE)])
        run(["git", "-C", str(SOURCE), "remote", "add", "origin", "https://github.com/sandbox-quantum/switch.git"])
        run(["git", "-C", str(SOURCE), "fetch", "--depth", "1", "origin", SWITCH_COMMIT])
        run(["git", "-C", str(SOURCE), "checkout", "--detach", "FETCH_HEAD"])
    actual = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip()
    if actual != SWITCH_COMMIT:
        raise SystemExit("Switch source differs from the audited pin; use a fresh .runtime/switch checkout.")
    if not (ROOT / ".env").exists():
        password = lambda: "Mw-" + secrets.token_hex(18)
        values = dict(
            COMPOSE_PROJECT_NAME="memoryweaver", COMPOSE_PROFILES="collab", SWITCH_VERSION="memoryweaver-source",
            SWITCH_BIND_ADDR="127.0.0.1", POSTGRES_HOST_PORT="55432", API_HOST_PORT="8000",
            DB_USER="switch_app", DB_PASSWORD=password(), DB_OWNER_USER="postgres", DB_OWNER_PASSWORD=password(), DB_NAME="switch",
            SECRET_KEYS="mw1:" + secrets.token_hex(32), AGENT_REGISTRATION_TOKEN=secrets.token_hex(32),
            GATEWAY_ADMIN_EMAIL="judge@memoryweaver.local", GATEWAY_ADMIN_PASSWORD=password(),
            FRONTEND_BASE_URL="http://localhost:8000", GATEWAY_COOKIE_SECURE="false",
            MATTERMOST_ADMIN_USER="mw-admin", MATTERMOST_ADMIN_PASSWORD=password(), MATTERMOST_TEAM_NAME="memoryweaver",
            MATTERMOST_USER="traveler", MATTERMOST_USER_PASSWORD=password(), WEB_INTERNAL_TOKEN=secrets.token_hex(32),
            AI_MODE="replay", PUBLISH_ENABLED="false", TELEMETRY_ENABLED="false", THIRD_PARTY_AVATARS_ENABLED="false",
        )
        fd = os.open(ROOT / ".env", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write("# Local generated secrets. Never commit. Set AI_MODE=live after authentication.\n")
            f.write("\n".join(k + "=" + v for k, v in values.items()) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["up", "down", "logs", "status", "credentials", "seed", "auth", "compose", "prepare"])
    p.add_argument("rest", nargs=argparse.REMAINDER)
    args = p.parse_args()
    prepare()
    compose = ["docker", "compose", "--project-directory", str(ROOT), "--env-file", str(ROOT / ".env"), "-f", str(SOURCE / "deploy/local/standalone-docker-compose.yml"), "-f", str(ROOT / "compose.yaml")]
    if args.command == "up":
        run(compose + ["up", "-d", "--build", "--remove-orphans"])
        print("\nMemoryWeaver http://localhost:8787\nMattermost http://localhost:8065\nRun python3 scripts/dev.py credentials for your local sign-in.")
    elif args.command == "credentials":
        values = dict(line.split("=", 1) for line in (ROOT / ".env").read_text().splitlines() if line and not line.startswith("#"))
        for key in ["MATTERMOST_USER", "MATTERMOST_USER_PASSWORD", "GATEWAY_ADMIN_EMAIL", "GATEWAY_ADMIN_PASSWORD"]:
            print(f"{key}={values[key]}")
    elif args.command == "auth":
        provider = args.rest[0] if args.rest else ""
        commands = {"claude": ["storyteller", "claude", "auth", "login"], "codex": ["editor", "codex", "login", "--device-auth"]}
        if provider not in commands:
            raise SystemExit("Usage: python3 scripts/dev.py auth claude|codex")
        run(compose + ["exec"] + commands[provider])
    elif args.command == "seed":
        run(compose + ["run", "--rm", "--no-deps", "-T", "bootstrap", "python", "-m", "scripts.seed"] + args.rest)
    elif args.command != "prepare":
        commands = {"down": ["down"], "status": ["ps", "-a"], "logs": ["logs", "--tail", "80"], "compose": []}
        run(compose + commands[args.command] + args.rest)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        # Preserve the tool's exit code without drowning useful provider/setup
        # messages in a Python wrapper traceback.
        raise SystemExit(exc.returncode)
