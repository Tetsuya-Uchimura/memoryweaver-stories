# Switch Console workflow

Use your own authenticated **Claude Code** and **Codex** providers on your computer, with Collector, Publisher, Mattermost and the private book application in Docker. This mode uses real model sessions managed by the official Console. Host authentication is never copied into Docker. GitHub/Cloudflare accounts are unnecessary.

## Start in an independent clone

1. Install Docker, Git and Python 3.9+. Run `python3 scripts/dev.py up`. Run `python3 scripts/dev.py seed --all --generate` after setup to create three English fictional chat/book fixtures, each explicitly labeled REPLAY. A normal Collector request after binding performs actual native inference.
2. Install the official [Switch Console](https://github.com/sandbox-quantum/switch/releases). The tested desktop version is **0.40.1**, against our pinned core version 0.31.0 / Gateway contract 1. Sign in to Claude Code and Codex under Settings → Agent providers on **This computer**. Provider authentication and account-specific model selection remain human operations.
3. Add an existing server: name **MemoryWeaver Docker**, server address **http://localhost:8000**. Run `python3 scripts/dev.py credentials` privately and use its `GATEWAY_ADMIN_EMAIL` and `GATEWAY_ADMIN_PASSWORD`. Link the Mattermost **traveler** account. This is separate from Console's own Local Switch server.
4. Prepare the role directories using the standard library only:

   ```sh
   python3 scripts/console.py prepare
   ```

   Default output: `~/Documents/MemoryWeaver Agents/storyteller` and `editor`. `--directory /absolute/path` overrides the parent. Preparation updates only the project role guides and JSON schemas, preserving Console's credential/session files.
5. On **MemoryWeaver Docker → Your Agents**, register two separate agents:

   | Field | Storyteller | Editor |
   | --- | --- | --- |
   | Name | `mw-storyteller-claude` | `mw-editor-codex` |
   | Provider | Claude Code | Codex |
   | Directory | Prepared `storyteller` directory | Prepared `editor` directory |
   | Instructions | `Follow CLAUDE.md and album.schema.json. Handle MW_CONSOLE through Switch.` | `Follow AGENTS.md and editorial.schema.json. Handle MW_DRAFT through Switch.` |
   | Run location | This computer | This computer |
   | Auto mode | On | On |
   | Bypass permissions | Off | Off |
   | Who can talk | Anyone | Anyone |

   Add both to **kyoto-travel-journal**, **paris-travel-journal**, and **new-york-travel-journal** using **Add to room**. Existing bound agents are automatically invited to newly provisioned sample rooms during an upgrade. `Rooms: any` is an addressing permission, not automatic membership in every room. Anyone is needed because bootstrap's tool agents have a different owner; room membership still limits access. A server with agent management disabled is supported: Console runs the provider processes locally.

   Choose a model available to **your** account. In the tested ChatGPT account, the old global `gpt-5.2-codex` default failed; choosing available `gpt-6.1-sol` under Advanced configuration and restarting the native agent resolved it. This project never changes your global model settings.
6. Bind the registered agents:

   ```sh
   python3 scripts/console.py bind
   ```

   The command uses the local generated Gateway login, verifies both providers, room membership and addressing policy, then saves **names and IDs only** through the protected local configuration endpoint. It refuses to change bindings during a working job. Custom names are supported with matching `--storyteller NAME --editor NAME` on both preparation and binding. Existing books and photos are retained.
7. Keep Console and Docker running. In Mattermost, send:

   ```text
   @mw-collector Create an English travel journal of our Kyoto trip. Keep every source, photograph and supplied location. Do not publish.
   ```

8. Receive Publisher's title, version URL, cover image and PDF in the same channel. Open `http://localhost:8787/` to follow the latest edition. Ask `@mw-collector Use the bamboo grove photograph as the cover.` and receive a new version and PDF. No production publishing occurs.

## What actually collaborates

Collector reads the authoritative room history, sanitizes new photographs, and creates the original evidence document in Switch. It targets the native Claude agent with `MW_CONSOLE`, its document ID, original thread and protocol instructions. Claude loads that document, creates a schema-valid draft, and sends `MW_DRAFT` to **both native Codex and Publisher**. Codex loads the original evidence and draft, creates a reviewed artifact, and sends `MW_REVIEW` to Publisher.

Publisher accepts those messages only from the bound authoritative Switch participant IDs. It records the genuine draft receipt and checks document hashes, job IDs, the review's draft reference, evidence citations and verbatim quotes before committing the private preview and durable PDF-delivery intent. All creative artifacts and handoffs travel through **Switch documents and targeted messages**. SQLite holds version state, binding and delivery/processing receipts; it is not an alternate model-message channel. Original Docker writer/reviewer workers idle for native jobs, avoiding duplicate inference and unauthenticated container CLI calls. The explicitly requested `[DEMO REPLAY]` fixture path uses their deterministic extractive renderer; it never calls unauthenticated provider CLIs. No replay fallback runs when Console is unavailable.

A saved native edition displays **LIVE AI**; a saved fixture keeps **REPLAY DEMO**. The web distinguishes Console-managed model roles from connected Docker tool agents. A configured Console role is not presented as proof that inference is currently running. Registration, provider login, membership, running session and successful generation are separate states.

## Practical limits and recovery

The provisioned Kyoto, Paris, New York and Santorini rooms each have a separate book database, sources, assets, revisions and PDF queue. Upgrades retire the obsolete pre-showcase room and archive its private data locally outside the web app. Use the trip selector or `?trip=kyoto`; versions are scoped to the selected trip. Arbitrary extra rooms do not automatically become books: the preconfigured trip catalog defines supported rooms. There is no application photo-count cutoff during collection; per-file sanitization and Switch size limits still apply. Console models choose their own photo inspection tools; this mode does not call the Docker Codex harness with its eight-image limit. This is not a guarantee that every photo was visually examined.

Keep the prepared role guides in the selected directories. Pending model permissions, provider sign-out, unsupported models and Console shutdown are visible in Console/Mattermost; we never claim the preview changed before Publisher succeeds. An abandoned job expires when the next request arrives after 15 minutes. Ask a fresh Collector request after fixing the session. Publisher retries artifact delivery and can resend a saved version with `@mw-publisher resend PDF vN`. Exact-version public consent remains a separate operation.

A fresh clone defaults to the Kyoto book and can generate all four replay fixtures without model accounts. The original container-CLI live mode is also supported when no Console binding exists. The replay smoke script refuses Console-bound data; use a separate fresh Docker project for replay checks. To inspect locally saved role bindings, use `/api/state`'s `runtime` and role names; credentials are never returned.

## Verify a live run

After posting a Collector request in Mattermost, run this observer with the version number from before that request (`1` after the initial replay fixture; `0` when no book exists):

```sh
python3 scripts/dev.py compose run --rm --no-deps -T bootstrap \
  python -m scripts.console_smoke --trip kyoto --after 1 --edit
```

`--edit` also posts a clearly labeled cover-change test to the selected Mattermost channel, choosing another source photograph so the cover actually changes. It requires two source photographs. The script waits for real native inference, confirms a bound Claude draft receipt and live saved revision, retains the previous photos, checks the Publisher bot identity and version-specific link, and compares both Mattermost attachments byte-for-byte with the saved PDF/cover. The HTTP PDF must match too. Publication state must remain unchanged. This uses the judge's own generated local account and does not approve an export or deploy anything. Inference latency and provider availability affect the result; timeout defaults to 600 seconds per generation.

For technical rendering questions, Editor can target Publisher with `MW_RENDERER_QUERY {"job_id":"..."}`. Publisher replies through Switch with `MW_RENDERER_REPLY` and the supported renderer contract. An unapproved review leaves the preview unchanged in clarification state; a corrected approved review may finish the same job. A newer Collector request supersedes that pending job and prevents its later review from overwriting the new work.
