"""Durable private completion delivery, entirely through Switch's media API."""
from __future__ import annotations

import asyncio
import time

from agents.artifacts import album_url, artifact_paths, render_artifacts
from agents.publish import approval_command


def completion_caption(revision):
    version = revision["version"]
    # User/model-authored titles cannot create Mattermost mentions or links.
    title = revision["album"]["title"].translate(str.maketrans({"@": "＠", "[": "［", "]": "］", "*": "＊", "`": "｀", "\n": " ", "\r": " "}))
    heading="Your travel journal is ready" if version==1 else "Your travel journal has been updated"
    return f"### {heading} 📖\n\n**{title}**\n\nWeb album: {album_url(version,revision.get('trip_id'))}\n\nThe cover preview and this edition’s PDF are attached. Visit stops and photo locations are included when supplied; sample pins are approximate fictional landmarks.\nAsk @mw-collector for changes in this channel.\n\nPrivate local edition. Public publication requires separate exact-version human approval:\n`{approval_command(revision)}`\n\nMemoryWeaver · v{version} · {revision['mode'].upper()}"



class DeliveryManager:
    def __init__(self, store, client):
        self.store = store
        self.client = client
        self.lock = asyncio.Lock()
        with store.connect() as db:
            # A stopped process may have left a render or request unfinished.
            db.execute("UPDATE deliveries SET state='pending' WHERE state IN ('rendering','sending')")

    async def existing_receipt(self, revision):
        version = revision["version"]
        required = {f"MemoryWeaver-v{version}.pdf", f"MemoryWeaver-cover-v{version}.jpg"}
        marker = f"MemoryWeaver · v{version} · {revision['mode'].upper()}"
        for entry in reversed(await self.client.history()):
            if entry.get("sender_kind") == "agent" and entry.get("sender_name") == "mw-publisher" and marker in entry.get("body", "").splitlines() and required.issubset({a["filename"] for a in entry.get("attachments", [])}):
                return {"event_id": entry["id"], "recovered": True}
        return None

    async def process(self, version):
        async with self.lock:
            delivery = self.store.delivery(version)
            if not delivery or delivery["state"] == "sent":
                return
            revision = self.store.revision(version)
            attempt = delivery["attempts"] + 1
            try:
                self.store.delivery_update(version, "rendering", attempt)
                pdf, cover, manifest = await asyncio.to_thread(render_artifacts, self.store, revision)
                # Recover an accepted upload after a lost HTTP response/restart.
                receipt = await self.existing_receipt(revision)
                caption = completion_caption(revision)
                if receipt is None:
                    self.store.delivery_update(version, "sending", attempt)
                    receipt = await self.client.upload([
                        (cover.name, cover.read_bytes(), "image/jpeg"),
                        (pdf.name, pdf.read_bytes(), "application/pdf"),
                    ], caption)
                receipt = {**receipt, **manifest, "url": album_url(version,revision.get("trip_id")), "sent_at": time.time()}
                self.store.delivery_update(version, "sent", attempt, receipt=receipt)
                self.store.event("publisher", caption, "complete")
            except Exception as exc:
                safe = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
                state = "retrying" if attempt < 5 else "failed"
                self.store.delivery_update(version, state, attempt, time.time() + min(60, 2 ** attempt), error=safe[:400])
                self.store.event("publisher", f"v{version}: private artifact delivery {state} ({safe[:400]})", "error")
                if attempt == 1:
                    # The book is already saved; report an attachment failure separately.
                    try:
                        await self.client.say(f"Your journal v{version} has been saved: {album_url(version,revision.get("trip_id"))}\nRetrying cover and PDF delivery. If they do not arrive, send `@mw-publisher resend PDF v{version}`.")
                    except Exception:
                        pass

    async def run(self):
        while True:
            await self.client.connected.wait()
            with self.store.connect() as db:
                versions = [row[0] for row in db.execute("SELECT revision FROM deliveries WHERE state IN ('pending','retrying') AND next_attempt<=? ORDER BY revision", (time.time(),))]
            for version in versions:
                await self.process(version)
            await asyncio.sleep(2)
