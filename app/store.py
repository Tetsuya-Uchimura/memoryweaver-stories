from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import sqlite3
import time
import uuid


class Store:
    def __init__(self, directory=None):
        self.root = Path(directory or os.getenv("DATA_DIR", ".runtime/data"))
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "media").mkdir(exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS assets (id TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS revisions (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, job_id TEXT UNIQUE, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, message TEXT, kind TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, request TEXT, base INTEGER, state TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS handled (role TEXT, event TEXT, PRIMARY KEY(role,event));
            CREATE TABLE IF NOT EXISTS approvals (revision INTEGER PRIMARY KEY, digest TEXT, user_id TEXT, event_id TEXT, created REAL, state TEXT, url TEXT);
            CREATE TABLE IF NOT EXISTS deliveries (revision INTEGER PRIMARY KEY, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0, error TEXT, receipt TEXT);
            """)

    def connect(self):
        db = sqlite3.connect(self.root / "memoryweaver.sqlite", timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def get(self, key, default=None):
        with self.connect() as db:
            row = db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, json.dumps(value, ensure_ascii=False)))

    def put(self, table, value):
        if table not in ("sources", "assets"):
            raise ValueError("Unknown table")
        with self.connect() as db:
            db.execute(f"INSERT OR REPLACE INTO {table} VALUES (?,?)", (value["id"], json.dumps(value, ensure_ascii=False)))

    def all(self, table):
        if table not in ("sources", "assets"):
            raise ValueError("Unknown table")
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute(f"SELECT data FROM {table} ORDER BY rowid")]

    def revision(self, version=None):
        with self.connect() as db:
            row = db.execute("SELECT * FROM revisions WHERE id=?", (version,)).fetchone() if version else db.execute("SELECT * FROM revisions ORDER BY id DESC LIMIT 1").fetchone()
            if not row:return None
            value={"version": row["id"], "created": row["created"], **json.loads(row["data"])}
            if self.get("trip"):value["trip_id"]=self.get("trip")["id"]
            return value

    def commit(self, album, job_id, mode, sources):
        from app.design import choose_design
        album = {**album, "design": choose_design(album, sources)}
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            last = db.execute("SELECT max(id) FROM revisions").fetchone()[0] or 0
            if not job or job["state"] not in {"working", "clarification"} or job["base"] != last:
                raise ValueError("Stale or completed job: request a new edit against the latest preview")
            asset_ids = set([album["cover_asset_id"], *[a for c in album["chapters"] for a in c["asset_ids"]]])
            known = {json.loads(r[0])["id"]: json.loads(r[0]) for r in db.execute("SELECT data FROM assets")}
            hashes = {}
            for asset_id in asset_ids:
                item = known[asset_id]
                path = Path(__file__).parent / "static/assets" / (asset_id + ".jpg") if item.get("sample") else self.root / "media" / (asset_id + ".jpg")
                hashes[asset_id] = hashlib.sha256(path.read_bytes()).hexdigest()
            from app.locations import snapshot_locations
            cited={sid for chapter in album["chapters"] for sid in chapter["source_ids"]}
            places,photo_locations=snapshot_locations([s for s in sources if s["id"] in cited],known,asset_ids)
            data = dict(album=album, mode=mode, sources=sources, asset_hashes=hashes, places=places, photo_locations=photo_locations, language=self.get("trip",{}).get("language","en"))
            cur = db.execute("INSERT INTO revisions(data,job_id,created) VALUES (?,?,?)", (json.dumps(data, ensure_ascii=False), job_id, time.time()))
            db.execute("UPDATE jobs SET state='complete' WHERE id=?", (job_id,))
            # The preview and its delivery intent are committed atomically.
            db.execute("INSERT INTO deliveries(revision,state) VALUES (?,'pending')", (cur.lastrowid,))
            return cur.lastrowid

    def revision_for_job(self, job_id):
        with self.connect() as db:
            row = db.execute("SELECT id FROM revisions WHERE job_id=?", (job_id,)).fetchone()
        return self.revision(row[0]) if row else None

    def delivery(self, version):
        with self.connect() as db:
            row = db.execute("SELECT * FROM deliveries WHERE revision=?", (version,)).fetchone()
        if not row:
            return None
        value = dict(row)
        value["receipt"] = json.loads(value["receipt"]) if value["receipt"] else None
        return value

    def queue_delivery(self, version):
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM revisions WHERE id=?", (version,)).fetchone():
                raise ValueError("That travel-book version does not exist")
            db.execute("INSERT INTO deliveries(revision,state) VALUES (?,'pending') ON CONFLICT(revision) DO UPDATE SET state='pending',attempts=0,next_attempt=0,error=NULL", (version,))

    def delivery_update(self, version, state, attempts, next_attempt=0, error=None, receipt=None):
        with self.connect() as db:
            db.execute("UPDATE deliveries SET state=?,attempts=?,next_attempt=?,error=?,receipt=COALESCE(?,receipt) WHERE revision=?", (state, attempts, next_attempt, error, json.dumps(receipt) if receipt is not None else None, version))

    def job(self, request, event_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM jobs WHERE id=?", (event_id,)).fetchone():
                return None
            db.execute("UPDATE jobs SET state='expired' WHERE state='working' AND created<?", (time.time() - 900,))
            # Concurrent edits must not silently overwrite one another.
            if db.execute("SELECT 1 FROM jobs WHERE state='working'").fetchone():
                raise ValueError("An edit is already in progress; wait for the preview, then resend your request")
            db.execute("UPDATE jobs SET state='superseded' WHERE state='clarification'")
            base = db.execute("SELECT max(id) FROM revisions").fetchone()[0] or 0
            db.execute("INSERT INTO jobs VALUES (?,?,?,'working',?)", (event_id, request, base, time.time()))
            return {"id": event_id, "base": base, "request": request}

    def event(self, role, message, kind="progress"):
        with self.connect() as db:
            db.execute("INSERT INTO events(role,message,kind,created) VALUES (?,?,?,?)", (role, message, kind, time.time()))

    def events(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT 100")][::-1]

    def finish_event(self, role, event):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO handled VALUES (?,?)", (role, event))

    def handled(self, role, event):
        with self.connect() as db:
            return bool(db.execute("SELECT 1 FROM handled WHERE role=? AND event=?", (role, event)).fetchone())
