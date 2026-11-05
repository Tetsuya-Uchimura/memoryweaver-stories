# Receive the finished travel book inside Mattermost

The private Mattermost room is both the place to request a book and the place to receive it. No GitHub or Cloudflare account is required for this feature, and sending a private PDF does not authorize public publication.

## The experience

1. Post travel photographs and memories in `kyoto-travel-journal` (or another provisioned trip channel).
2. Ask `@mw-collector Create an English travel journal from this room.`.
3. Collector, Storyteller, and Editor collaborate using Switch room documents and targeted handoffs.
4. Publisher saves the version in the local web application, renders its PDF, and sends **one top-level channel post** containing the title, a version-specific album URL, the cover JPEG, and the downloadable PDF.
5. Ask for an edit in the same channel, for example `@mw-collector Use the sunset photograph as the cover.`.
6. Receive a new completion post, cover, and PDF for the updated version. Previous posts still open their original versions.

The cover appears using Mattermost's native image attachment preview. The PDF is a real file attachment, not merely a URL or a browser print instruction. PDF layout includes a full-page photographic cover, English narration and quotations, chapter photography, page numbers, and photo credits/licenses. Its edition label distinguishes replay rendering from live AI writing.

## Run from a fresh clone

```sh
git clone https://github.com/Tetsuya-Uchimura/memoryweaver-stories.git
cd memoryweaver-stories
python3 scripts/dev.py up
python3 scripts/dev.py seed --generate
python3 scripts/dev.py credentials
```

Log in to [Mattermost](http://localhost:8065) as the generated traveler account and open the private channel. Wait for Publisher's completion post. The same setup works in a judge's independently initialized Docker stack. All credentials and bot identities are generated there; nothing authenticates to the developer's Mattermost installation.

Docker installs the pinned WeasyPrint renderer, its Pango/Harfbuzz system libraries, and **Noto CJK fonts**. No host browser, printer, GUI, PDF service, font installation, extra token, or manual bot configuration is needed. A PDF render runs in a worker thread so the Switch connection keeps receiving events and heartbeats.

Default preview links are `http://localhost:8787/?trip=kyoto&version=N`. If the operator has a different browser-facing preview address, set `ALBUM_BASE_URL` in the ignored `.env` and recreate services with `up`. It must be an HTTP(S) base URL without credentials or a query/fragment. Do not use the Docker-internal `http://web:8787` address in messages. The stack remains loopback-only; remote access still requires an appropriately authenticated operator-managed frontend.

## Switch's standard attachment transport

No direct Mattermost admin-token fallback was needed. The pinned official Switch implementation supports:

```text
POST /agents/{publisher_agent_id}/rooms/{room_id}/media
Authorization: Bearer <Publisher's own Switch agent API key>
Content-Type: multipart/form-data

caption: completion text and version-specific album URL
files: MemoryWeaver-cover-vN.jpg (image/jpeg)
files: MemoryWeaver-vN.pdf (application/pdf)
```

The route validates attachments and creates a shared attachment group. The official Mattermost adapter uploads the files and creates one post using its existing Publisher bot identity. Omitting `thread_id` places the finished work directly in the channel; normal progress and handoffs remain in the request thread.

Audited source:

- [Multipart endpoint](https://github.com/sandbox-quantum/switch/blob/6e4ade5269d65ee38060a9f43b77c5e5b3be2f10/core/switch_core/bridges/agent/api/handlers.py): `upload_media` accepts repeated `files`, `caption`, and optional `thread_id`.
- [Agent media implementation](https://github.com/sandbox-quantum/switch/blob/6e4ade5269d65ee38060a9f43b77c5e5b3be2f10/core/switch_core/bridges/agent/protocol/agent_core.py): `send_media` checks room posting access, validates the batch, and records attachment-group events.
- [Mattermost adapter](https://github.com/sandbox-quantum/switch/blob/6e4ade5269d65ee38060a9f43b77c5e5b3be2f10/core/switch_core/bridges/collaboration/mattermost/adapter.py): `send_attachments` uses the bot's files API and one post with both file IDs.

The generation handoff, PDF attachment group, and completion caption therefore all pass through Switch. Publisher receives no Mattermost administrator credentials.

## Recovery and version consistency

The preview version and its pending delivery are committed in the same SQLite transaction. A stopped/restarted Publisher resumes pending deliveries. Sending failure does not roll back a saved book or require another model call. Automatic retries use increasing delays, up to five attempts. A first failure posts the available web link and explains that attachments will be retried.

To check/retry a failed delivery in Mattermost:

```text
@mw-publisher resend PDF v3
```

Use the actual version, or omit it for the latest version. An already accepted complete attachment group is recognized through the Publisher's authoritative Switch history, avoiding a duplicate completion post. A copied caption from a human does not count as a receipt. This is a check-and-retry command, not an instruction to duplicate a file that is already present in the channel.

Each PDF is cached at `/data/books/vN/MemoryWeaver-vN.pdf`; cover and integrity metadata live beside it. Its local download route is `/api/revisions/N/pdf`. The PDF and cover are generated from the saved version and its checked photo-byte hashes. They contain the selected book, not the full source transcript or unused photos. Rendering is restricted to an explicit in-memory image allowlist; external URLs and local file reads are rejected.

Switch acceptance and downstream Mattermost delivery are asynchronous. History reconciliation reduces duplicate sends after a lost response, but does not claim distributed exactly-once delivery across every possible server crash. The end-to-end smoke check independently downloads both actual Mattermost files and compares their hashes to the saved version.

## Verify

```sh
python3 scripts/dev.py compose run --rm --no-deps -T bootstrap python -m scripts.smoke
```

This uses real Mattermost and Switch in replay mode with public publishing disabled. It verifies initial delivery and two edited versions, the Publisher bot identity, top-level channel placement, title and version URL, both actual attachments, PDF bytes, changed cover bytes, and the local PDF download route. A human retry also reconciles the actual Switch attachment group without duplicate posts or regenerated books. It retains the publication-consent checks. The complete check passed in an independently initialized Docker project from a fresh GitHub clone; see [verification](VERIFICATION.md).

For host-side unit tests, WeasyPrint needs Pango installed. On Apple Silicon with Homebrew libraries, use `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib .venv/bin/python -m pytest -q`. Docker includes all native libraries and Japanese fonts automatically; judges do not need this host-specific setup.


Trips have separate revision numbers, PDF caches and outbox receipts. New completion links include the trip ID; e.g. `/api/revisions/2/pdf?trip=kyoto` downloads Kyoto edition 2. Photo locations and the trip’s supplied stops are included in the PDF. Unknown places are not guessed. Legacy unqualified completion/PDF URLs continue to resolve to retained old editions after an upgrade.
