#!/usr/bin/env python3
"""Prepare portable Console workspaces and bind registered model agents.

Uses Python's standard library only. Never imports/copies provider credentials.
"""
import argparse
import http.cookiejar
import json
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def request(opener, url, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None, headers=headers)
    with opener.open(req, timeout=30) as response:
        return json.load(response)


def prepare(directory, storyteller, editor):
    for role in ["storyteller", "editor"]:
        target = directory / role
        target.mkdir(parents=True, exist_ok=True)
        for source in (ROOT / "agents/console-workspaces" / role).iterdir():
            text = source.read_text().replace("mw-storyteller-claude", storyteller).replace("mw-editor-codex", editor)
            (target / source.name).write_text(text)
        print(role + " directory: " + str(target.resolve()))


def bind(values, storyteller, editor):
    base = "http://localhost:" + values.get("API_HOST_PORT", "8000")
    web = "http://localhost:" + values.get("WEB_HOST_PORT", "8787")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    request(opener, base + "/gateway/auth/login", {"email": values["GATEWAY_ADMIN_EMAIL"], "password": values["GATEWAY_ADMIN_PASSWORD"]})
    try:
        catalog=request(opener,web+"/api/trips")
        room_name=next((t["channel"] for t in catalog["trips"] if t["id"]==catalog["default"]),"kyoto-travel-journal")
        agents = request(opener, base + "/gateway/agents")
        result = {}
        for role, name in [("storyteller", storyteller), ("editor", editor)]:
            matches = [a for a in agents if a["name"] == name]
            if len(matches) != 1:
                raise ValueError("Register exactly one Console agent named " + name)
            agent = matches[0]
            expected = "Claude Code" if role == "storyteller" else "Codex CLI"
            if agent["connector_type"] != expected:
                raise ValueError(name + " must use " + expected)
            detail = request(opener, base + "/gateway/agents/" + agent["id"])
            if not any(r["room_name"] == room_name and not r.get("archived") for r in detail["rooms"]):
                raise ValueError("Use Add to room to join "+room_name+": " + name)
            if detail.get("addressing_policy") is not None:
                raise ValueError("Use Who can talk: Anyone so bootstrap-owned tool agents can hand off: " + name)
            result[role] = {"id": agent["id"], "name": name}
        request(opener, web+"/internal/console", result, values["WEB_INTERNAL_TOKEN"])
        print("Console runtime bound: " + storyteller + " → " + editor + " → mw-publisher")
    finally:
        request(opener, base + "/gateway/auth/logout", {})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["prepare", "bind"])
    p.add_argument("--directory", type=Path, default=Path.home()/"Documents/MemoryWeaver Agents")
    p.add_argument("--storyteller", default="mw-storyteller-claude")
    p.add_argument("--editor", default="mw-editor-codex")
    args = p.parse_args()
    if args.command == "prepare":
        prepare(args.directory, args.storyteller, args.editor)
    else:
        # Local generated credentials, never command arguments or printed output.
        values = dict(line.split("=",1) for line in (ROOT/".env").read_text().splitlines() if line and not line.startswith("#"))
        bind(values, args.storyteller, args.editor)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, urllib.error.URLError) as exc:
        raise SystemExit(str(exc))
