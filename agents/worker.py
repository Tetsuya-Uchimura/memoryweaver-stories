from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
import httpx
from app.models import Album, Source, validate_evidence
from app.store import Store
from app.locations import ANNOTATION, parse_location
from agents.switch import Switch
from agents.models import harness, replay

ROLES = ["collector", "storyteller", "editor", "publisher"]
GENERATION = re.compile(r"\u30a2\u30eb\u30d0\u30e0|\u65c5\u884c\u8a18|\b(?:albums?|journals?|travelogue|generate|story|storybook)\b", re.I)
EDIT = re.compile(r"\u5909\u66f4|\u53cd\u6620|\u8ffd\u52a0|\u611f\u52d5|\u4fee\u6b63|\u3082\u3063\u3068|\u8868\u7d19|\b(?:cover|revise|edit|emotional|include|add)\b", re.I)
STAMP = re.compile(r"^\[(\d{4}-\d{2}-\d{2}T[^\]]+)\]\s*")


def instruction_text(body):
    return bool(GENERATION.search(body) or EDIT.search(body) or body.startswith(("PUBLISH ", "MemoryWeaver sample")) or "@mw-" in body)


class Worker:
    def __init__(self, role, trip=None):
        self.role = role
        self.root_store = Store()
        from app.trips import trip_store
        self.store = trip_store(self.root_store,trip) if trip else self.root_store
        self.trip_id = trip
        if trip:self.store.set("console",self.root_store.get("console"))
        state = self.store.get("switch")
        self.client = Switch(state["agents"][role], state["room_id"])
        self.mode = os.getenv("AI_MODE", "replay")
        self.queue = asyncio.Queue()
        if role == "publisher":
            from agents.delivery import DeliveryManager
            self.deliveries = DeliveryManager(self.store, self.client)

    async def report(self, message, thread=None, kind="progress"):
        self.store.event(self.role, message, kind)
        await self.client.say(message, thread)

    async def collect(self, entries):
        assets = self.store.all("assets")
        for entry in entries:
            if entry.get("kind") != "message" or entry.get("sender_kind") != "user":
                continue
            body = entry.get("body", "")
            match = STAMP.match(body)
            photographs = [a for a in entry.get("attachments", []) if a.get("mimetype", "").startswith("image/")]
            if not match and instruction_text(body):
                if not photographs:
                    continue
                # A request and its photographs are independent inputs. Keep
                # caption lines, but never quote an editing instruction as a memory.
                body = "\n".join(line for line in body.splitlines() if STAMP.match(line) or ANNOTATION.fullmatch(line) or not instruction_text(line)).strip()
                match = STAMP.match(body)
            if not body.strip() and not entry.get("attachments"):
                continue
            timestamp = datetime.fromtimestamp(entry["timestamp"] / 1000, timezone.utc).isoformat()
            if match:
                timestamp = datetime.fromisoformat(match[1]).isoformat()
                body = body[match.end():]
            old = next((s for s in self.store.all("sources") if s["id"] == entry["id"]), None)
            asset_ids = list(old["asset_ids"]) if old else []
            if not old:
                for attachment in photographs:
                    if attachment.get("size", 0) > 20 * 1024 * 1024:
                        raise ValueError("A photograph exceeds 20 MB; resize it and resend")
                    data = await self.client.download(attachment["mxc"])
                    # Sample attribution is granted only on an exact match with shipped bytes.
                    sample = next((a for a in assets if a.get("sample") and hashlib.sha256((Path("app/static/assets") / (a["id"] + ".jpg")).read_bytes()).digest() == hashlib.sha256(data).digest()), None)
                    if sample:
                        asset_ids.append(sample["id"])
                    else:
                        async with httpx.AsyncClient() as http:
                            response = await http.post(os.getenv("WEB_URL", "http://localhost:8787") + "/internal/media", headers={"Authorization": "Bearer " + os.environ["WEB_INTERNAL_TOKEN"]}, files={"file": ("photo.jpg", data, "image/jpeg")}, params={"trip":self.trip_id} if getattr(self,"trip_id",None) else {})
                            response.raise_for_status()
                            asset_ids.append(response.json()["id"])
            body,location = parse_location(body)
            source = Source(location=location,id=entry["id"], author=entry["sender_name"], text=body, captured_at=timestamp, date_basis="captured" if match else "posted", asset_ids=asset_ids)
            self.store.put("sources", source.model_dump())

    async def generate(self, entry, job_id=None):
        """Build evidence and hand off through Switch, including attached requests.

        An operator can recover a previously ignored attachment with a distinct
        processing job ID while retaining the original, authoritative source post.
        """
        event_id = entry["id"]
        thread = entry.get("thread_id") or event_id
        job = self.store.job(entry.get("body", ""), job_id or event_id)
        if not job:
            return
        console = self.root_store.get("console") if hasattr(self,"root_store") else self.store.get("console")
        demo = entry.get("body", "").startswith("@mw-collector [DEMO REPLAY]")
        mode = "replay" if demo else ("live" if console else self.mode)
        await self.report("I’m gathering the photographs and everyone’s words. Capture dates will guide the chapters; missing details stay unknown. · " + mode.upper() + (" · Switch Console" if console and mode=="live" else ""), thread)
        entries = await self.client.history()
        await self.collect(entries)
        sources = sorted(self.store.all("sources"), key=lambda s: s["captured_at"])
        if not sources:
            raise ValueError("Post memories and photographs before requesting an album")
        self.store.set("console",console)
        self.store.set("job-mode:"+job["id"],mode)
        trip=self.store.get("trip",{})
        payload = dict(job=job, sources=sources, assets=self.store.all("assets"), previous=self.store.revision(), mode=mode, language=trip.get("language","en"), destination=trip.get("destination"), trip_id=trip.get("id"), trip_title=trip.get("title"), trip_subtitle=trip.get("subtitle"))
        document_id = await self.client.document("evidence-" + hashlib.sha256(job["id"].encode()).hexdigest()[:12], payload)
        await self.report(f"Collected {len(sources)} source posts from {len(set(s['author'] for s in sources))} contributors. Evidence is shared in the Switch room document.", thread)
        if console and mode=="live":
            from agents.console import start
            await start(self, document_id, payload, thread)
        else:
            await self.client.handoff("storyteller", document_id, job, thread)

    async def handle(self, entry):
        event_id = entry["id"]
        if self.store.handled(self.role, event_id) or entry.get("kind") != "message":
            return
        if self.role in {"storyteller", "editor"} and self.store.get("console"):
            incoming=re.search(r"MW_HANDOFF (\{.*\})",entry.get("body",""),re.S)
            job_id=json.loads(incoming[1]).get("job",{}).get("id") if incoming else None
            if self.store.get("job-mode:"+str(job_id))!="replay":
                self.store.finish_event(self.role,event_id)
                return  # Only an explicitly requested demo uses Docker replay here.
        body = entry.get("body", "")
        thread = entry.get("thread_id") or event_id
        human = entry.get("sender_kind") == "user"
        if self.role == "collector" and human:
            if "PUBLISH " not in body and "@mw-publisher" not in body and ("@mw-collector" in body or GENERATION.search(body) or EDIT.search(body)) and not STAMP.match(body):
                await self.generate(entry)
            else:
                await self.collect([entry])
        elif self.role == "publisher" and human and body.startswith("PUBLISH "):
            from agents.publish import approve_and_publish
            if entry["sender_name"] != os.environ.get("MATTERMOST_USER", "traveler"):
                await self.report("Only the configured traveler account can approve publication.", thread, "error")
            else:
                message = await approve_and_publish(self.store, body, entry)
                await self.report(message, thread, "publication")
        elif self.role == "publisher" and human and "@mw-publisher" in body and re.search(r"\u518d\u9001|\u9001\u308a\u76f4|resend|retry", body, re.I):
            requested = re.search(r"\bv(\d+)\b", body, re.I)
            current = self.store.revision(int(requested[1])) if requested else self.store.revision()
            if not current:
                raise ValueError("Create a travel journal first. The requested edition could not be found.")
            self.store.queue_delivery(current["version"])
            await self.report(f"Checking the attachments for journal v{current['version']} and resending them if needed.", thread)
        if self.role == "publisher" and not human and self.store.get("console"):
            from agents.console import receive
            if await receive(self, entry):
                self.store.finish_event(self.role, event_id)
                return
            # Old Docker handoffs cannot commit a book in Console mode.
        if self.role != "collector" and not human:
            match = re.search(r"MW_HANDOFF (\{.*\})", body, re.S)
            expected = "mw-" + ROLES[ROLES.index(self.role) - 1]
            if match and entry.get("sender_kind") == "agent" and entry.get("sender_name") == expected:
                handoff = json.loads(match[1])
                payload = await self.client.load(handoff["document_id"])
                job = payload["job"]
                if self.store.get("console") and self.store.get("job-mode:"+job["id"])!="replay":
                    self.store.finish_event(self.role,event_id)
                    return
                if self.role == "storyteller":
                    await self.report("Weaving the memories into a story. Every chapter will carry the posts it came from. · " + payload["mode"].upper(), thread)
                    if payload["mode"] == "live":
                        album = await harness("claude", payload)
                    else:
                        await asyncio.sleep(2)
                        album = replay(payload)
                    validate_evidence(Album.model_validate(album), payload["sources"], {a for s in payload["sources"] for a in s["asset_ids"]})
                    payload["album"] = album
                    document_id = await self.client.document("draft-" + hashlib.sha256(event_id.encode()).hexdigest()[:12], payload)
                    await self.client.handoff("editor", document_id, job, thread)
                elif self.role == "editor":
                    await self.report("Checking the story against the original words, photo references, and dates. Unsupported details will be removed or returned for clarification.", thread)
                    if payload["mode"] == "live":
                        reviewed = await harness("codex", payload)
                    else:
                        await asyncio.sleep(2)
                        reviewed = dict(album=payload["album"], approved=True, notes=["Replay: extractive sample, quote and citation checks passed. No live model review."])
                    if not reviewed["approved"]:
                        raise ValueError("Editor needs clarification: " + "; ".join(reviewed["notes"]))
                    album = Album.model_validate(reviewed["album"])
                    validate_evidence(album, payload["sources"], {a for s in payload["sources"] for a in s["asset_ids"]})
                    payload["album"] = album.model_dump()
                    payload["review"] = reviewed["notes"]
                    payload["editor_approved"] = True
                    document_id = await self.client.document("review-" + hashlib.sha256(event_id.encode()).hexdigest()[:12], payload)
                    await self.client.handoff("publisher", document_id, job, thread)
                elif self.role == "publisher":
                    if not payload.get("editor_approved"):
                        raise ValueError("Missing editorial review")
                    album = Album.model_validate(payload["album"])
                    validate_evidence(album, payload["sources"], {a for s in payload["sources"] for a in s["asset_ids"]})
                    # Redelivered handoffs reuse the committed version. PDF work and
                    # notification run from a durable outbox, outside the SSE consumer.
                    existing = self.store.revision_for_job(job["id"])
                    if not existing:
                        self.store.commit(album.model_dump(), job["id"], payload["mode"], payload["sources"])
        self.store.finish_event(self.role, event_id)

    async def consume(self):
        while True:
            event = await self.queue.get()
            await self.client.connected.wait()
            try:
                # Durable history supplies authoritative sender_kind, not a user-controlled prefix.
                entries = await self.client.history()
                if event["type"] == "reconcile":
                    for entry in entries:
                        await self.handle_safely(entry)
                else:
                    payload = event["payload"]
                    entry = next((e for e in entries if e["id"] == payload["message_id"]), None)
                    if entry:
                        entry["thread_id"] = payload.get("thread_id")
                        await self.handle_safely(entry)
                    self.client.cursor = event.get("sequence", self.client.cursor)
            finally:
                self.queue.task_done()

    async def handle_safely(self, entry):
        try:
            await self.handle(entry)
        except Exception as exc:
            # Keep failed work visible and allow a fresh human request to recover.
            print(self.role, type(exc).__name__, flush=True)
            self.store.finish_event(self.role, entry["id"])
            job_id = entry["id"] if self.role == "collector" else None
            if self.role != "collector" and entry.get("sender_kind") == "agent":
                handoff = re.search(r"MW_HANDOFF (\{.*\})", entry.get("body", ""), re.S)
                if handoff:
                    try:
                        job_id = json.loads(handoff[1])["job"]["id"]
                    except (ValueError, KeyError, TypeError):
                        pass
                native = re.search(r"MW_(?:DRAFT|REVIEW) (\{[^\n]*\})", entry.get("body", ""))
                if native:
                    try:
                        job_id = json.loads(native[1])["job_id"]
                    except (ValueError, KeyError, TypeError):
                        pass
            with self.store.connect() as db:
                db.execute("UPDATE jobs SET state='failed' WHERE id=? AND state='working'", (job_id,))
            safe = str(exc) if isinstance(exc, ValueError) else f"{self.role} could not complete this step ({type(exc).__name__}). Check local service logs/authentication and resend the request."
            await self.report(safe[:800], entry["id"], "error")

    async def health(self):
        while True:
            binding = self.store.get("console")
            if binding and self.role in {"storyteller", "editor"}:
                # Registered/room presence does not prove a provider session is live.
                self.store.set("health:" + self.role, {"status": "console", "at": time.time(), "mode": "live", "name": binding[self.role]["name"]})
            else:
                self.store.set("health:" + self.role, {"status": "connected" if self.client.connected.is_set() else "reconnecting", "at": time.time(), "mode": "live" if binding else self.mode})
            await asyncio.sleep(3)

    async def run(self):
        tasks = [self.client.listen(self.queue), self.consume(), self.health()]
        if self.role == "publisher":
            tasks.append(self.deliveries.run())
        await asyncio.gather(*tasks)


async def run_role(role):
    root=Store()
    trips=root.get("trips")
    if not trips:
        await Worker(role).run()
    else:
        await asyncio.gather(*(Worker(role,t["id"]).run() for t in trips))


if __name__ == "__main__":
    asyncio.run(run_role(os.environ["AGENT_ROLE"]))
