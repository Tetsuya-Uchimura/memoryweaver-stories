# Switch architecture and source audit

Audit date: November 5, 2026. Upstream: https://github.com/sandbox-quantum/switch. Pin: **6e4ade5269d65ee38060a9f43b77c5e5b3be2f10**. Never replace this with an unreviewed `main` or `latest` tag.

The source pin is fetched by Git and checked on every launcher invocation. We build the official core and setup Dockerfiles rather than guessing a published image tag; upstream Console release versions and server registry versions are not interchangeable.

## Audited contracts

All links below point to the exact source revision used by the project.

| Concern | Upstream source | MemoryWeaver use |
| --- | --- | --- |
| Standalone infrastructure | [Compose](https://github.com/sandbox-quantum/switch/blob/6e4ade5269d65ee38060a9f43b77c5e5b3be2f10/deploy/local/standalone-docker-compose.yml) | Layer `compose.yaml` on it using `--project-directory` so contexts resolve consistently |
| Mattermost/team/account/bridge setup | [setup.py](https://github.com/sandbox-quantum/switch/blob/6e4ade5269d65ee38060a9f43b77c5e5b3be2f10/deploy/shared_resources/setup.py) | Execute unchanged; includes gateway-cookie login and owner identity linking |
| Registration and heartbeat schemas | [schemas.py](https://github.com/sandbox-quantum/switch/blob/6e4ade5269d65ee38060a9f43b77c5e5b3be2f10/core/switch_core/bridges/agent/api/schemas.py) | `POST /agents` with registration key; agent API keys are separate credentials |
| SSE and media HTTP routes | [handlers.py](https://github.com/sandbox-quantum/switch/blob/6e4ade5269d65ee38060a9f43b77c5e5b3be2f10/core/switch_core/bridges/agent/api/handlers.py) | `GET /agents/{id}/events`, `POST .../connection/beat`, room-scoped attachment downloads and multipart uploads of the cover/PDF group |
| Wire encoding and initial state | [stream.py](https://github.com/sandbox-quantum/switch/blob/6e4ade5269d65ee38060a9f43b77c5e5b3be2f10/core/switch_core/bridges/agent/protocol/stream.py) | Read SSE `event:` as well as `data:`; control-frame data does not contain `type` |
| Operation signatures | [definitions.py](https://github.com/sandbox-quantum/switch/blob/6e4ade5269d65ee38060a9f43b77c5e5b3be2f10/core/switch_core/bridges/agent/operations/definitions.py) | Discover registry at startup; invoke raw arguments, not a fabricated RPC wrapper |
| Example custom-client bootstrap | [official e2e harness](https://github.com/sandbox-quantum/switch/blob/6e4ade5269d65ee38060a9f43b77c5e5b3be2f10/core/tests/e2e/follow_the_conversation/harness.py) | Reference for agent registration, bridge selection, and room creation |

The upstream [agent protocol document](https://github.com/sandbox-quantum/switch/blob/6e4ade5269d65ee38060a9f43b77c5e5b3be2f10/docs/official/internals/agent-protocol.md) is useful context, but we verified its claims against the running source. The current source also has a newer WebSocket transport. SSE remains supported for protocol revision 7. We deliberately pin to that compatibility contract.

## Details discovered in real testing

1. **Control events:** `connection_state`, `gap`, and `evicted` have their kind on the SSE `event:` line, not necessarily in their JSON data. The client parses both.
2. **Fenced heartbeats:** a protocol-7 heartbeat must include the `generation` from the initial `connection_state`. Omitting it produces an explicit 409. The advertised heartbeat interval is honored, independently of model calls.
3. **Sender provenance:** the pinned `read_context` path may omit `sender_kind`. The client resolves opaque senders from server-generated room-join records and the current participant roster, matching the unique Mattermost username. It does not infer an actor type by splitting an ID or accept a text prefix as proof of identity.
4. **History:** `read_context` returns thread groups. Pagination uses ISO `before` dates converted from millisecond `oldest_timestamp`; `truncated` is checked. A human correction cannot be ignored merely because it fell outside a fixed 50-message window.
5. **Documents:** only their creating agent can update them. We create distinct immutable evidence, draft, and review documents per generation instead of having agents overwrite each other’s documents.
6. **Tasks:** upstream labels its task protocol not ready for use. We use the supported `send_targeted_message` and room-document operations instead.

## Console-managed provider integration

See [Console setup and wire protocol](CONSOLE.md). In this mode Collector targets the registered native Claude agent, whose `MW_DRAFT` addresses both native Codex and Publisher. Codex's `MW_REVIEW` references that exact draft. Publisher matches authoritative participant IDs, pins original evidence and draft hashes, and validates the reviewed album before saving. Drafts are untrusted editorial input: Editor can correct a malformed date or unsupported quote, but the final review must pass strict schema and evidence checks. Docker writer/reviewer workers do not run inference in Console mode.

Setup uses the pinned Gateway's real login, agent-list and agent-detail endpoints after Console registration. It stores no provider secrets. The installed Console runs on the host; Docker's `agent_management=false` does not prevent this local execution path. We do not manipulate Console's SQLite or synthesize provider sessions.

## Sequence and shared context

```mermaid
sequenceDiagram
    participant H as Travelers / Mattermost
    participant S as Switch room
    participant C as Collector
    participant W as Storyteller / Claude Code
    participant E as Editor / Codex
    participant P as Publisher
    H->>S: Photos, comments, make a book
    S->>C: Human message event
    C->>S: Read full human context and download referenced media
    C->>S: Create evidence document; target Storyteller
    S->>W: Handoff
    W->>S: Load evidence; save structured draft; target Editor
    S->>E: Handoff
    E->>S: Load draft; save checked review or ask human to clarify
    E->>S: Target Publisher after evidence validation
    S->>P: Handoff
    P->>P: Commit local preview version and delivery intent; render PDF
    P->>S: Standard multipart media: title, version URL, cover and PDF
    S->>H: Publisher bot posts both attachments in the original channel
    H->>S: Natural-language revision / factual clarification
    S->>C: Start a new version with shared context
```

The web application provides version storage, photo sanitization, and a projection of the actual collaboration events. It cannot start AI generation or approve publication through a browser write API. No browser token is shipped. In container-CLI mode, model child processes receive a filtered environment without Switch, Mattermost, web-internal, or publishing credentials. Console-managed providers use Switch’s own agent session credentials; their separate role directories contain only project guides/schemas and Console-managed session files, never the Docker `.env` or publisher token.

Publisher uses its own Switch agent key for attachment delivery; Switch's official Mattermost adapter uses the bot identity it already manages. No direct Mattermost-token fallback is required. See [Mattermost delivery](MATTERMOST-DELIVERY.md) for exact audited media paths, retry behavior, and the private PDF boundary. Cloud publication still requires separate exact-version human consent.

## Retry and recovery limits

Each process opens one stable connection ID per process lifetime, specifies its room at stream-open time, sends fenced heartbeats, and reconnects. On startup, reconnect, or `gap`, it reconciles durable room history using per-role processing receipts. Replaying a processed event cannot create another preview version. A job records its base revision and rejects stale commits. Simultaneous requests are refused visibly.

This is at-least-once infrastructure with a bounded MVP worker, not a transactional distributed workflow engine. A crash precisely between creating a document and recording its handoff can require a fresh human request; duplicate artifact names fail visibly. Jobs abandoned by a crash expire after 15 minutes. Restarting an upstream server, a worker, or the full local stack is part of the smoke/restart checks; no provider session is assumed to survive a failed model call.

Each provisioned travel room has its own book database and Switch session per role. The catalog includes Kyoto, Paris and New York, plus a preserved legacy room on upgrade. The container-CLI Codex Editor receives up to eight sanitized image attachments for visual review; Console-managed providers use their native Switch tools instead; text posts remain the authority for travel events and dates. Automatic geocoding/identity inference, arbitrary room-to-book creation, multi-tenant access and a general-purpose agent planner remain outside this implementation. Supplied place/GPS records, not model guesses, populate per-trip location snapshots.
