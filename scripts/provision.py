"""Runs after the unmodified official Switch setup job. Safe to re-run."""
import asyncio
import json
import os
from pathlib import Path
import httpx
from app.store import Store
from agents.switch import Switch

ROLES = {"collector": "Organizes photographs and cited human memories", "storyteller": "Claude Code travel writer; uses only cited evidence", "editor": "Codex editor and factual reviewer", "publisher": "Builds private previews and requires human publication approval"}


async def main():
    store = Store()
    saved = store.get("switch", {"agents": {}})
    async with httpx.AsyncClient(base_url=os.environ["SWITCH_URL"], timeout=60) as http:
        for role, description in ROLES.items():
            agent = saved["agents"].get(role)
            if agent:
                check = await http.get(f"/agents/{agent['id']}/ops", headers={"Authorization": "Bearer " + agent["api_key"]})
                if check.status_code == 200:
                    continue
                raise RuntimeError("Saved agent key is invalid; refusing to rotate a live agent implicitly")
            response = await http.post("/agents", headers={"Authorization": "Bearer " + os.environ["AGENT_REGISTRATION_TOKEN"]}, json={"name": "mw-" + role, "display_name": role.capitalize(), "description": description, "connector_type": "custom", "integration_profile": {"connection_model": "always_on", "message_exchange": True, "pre_invocation_mediation": [], "post_invocation_mediation": [], "event_reporting": []}})
            response.raise_for_status()
            saved["agents"][role] = response.json()
            store.set("switch", saved)
    clients = {role: Switch(agent) for role, agent in saved["agents"].items()}
    # Settings are owner-managed; a sibling agent configures each agent, never itself.
    for role, client in clients.items():
        sibling = clients["editor"] if role == "collector" else clients["collector"]
        await sibling.op("update_agent_detail", agent_id=client.agent["id"], addressing="anyone")
    collector = clients["collector"]
    # Provision the English judge showcase and retire obsolete sample journals.
    from scripts.trip_setup import provision_trips
    await provision_trips(store,saved,collector)
    from scripts.english_setup import english_protocol_history
    await english_protocol_history(store)
    # The web initializes SQLite as root; agents run as an unprivileged user.
    Path("/home/weaver/.codex").mkdir(parents=True, exist_ok=True)
    Path("/home/weaver/.claude").mkdir(parents=True, exist_ok=True)
    for base in [store.root, Path("/home/weaver")]:
        for root, dirs, files in os.walk(base):
            os.chown(root, 1000, 1000)
            for filename in files:
                os.chown(Path(root) / filename, 1000, 1000)
    for client in clients.values():
        await client.http.aclose()
    print("MemoryWeaver agents and private Mattermost room provisioned. No AI or publishing credentials were imported.")


if __name__ == "__main__":
    asyncio.run(main())
