# Switch architecture and source audit

Audit date: November 4, 2026. Upstream: https://github.com/sandbox-quantum/switch. Pin: **6e4ade5269d65ee38060a9f43b77c5e5b3be2f10**. Never replace this with an unreviewed `main` or `latest` tag.

The source pin is fetched by Git and checked on every launcher invocation. We build the official core and setup Dockerfiles rather than guessing a published image tag; upstream Console release versions and server registry versions are not interchangeable.

## Audited contracts

All links below point to the exact source revision used by the project.

| Concern | Upstream source | MemoryWeaver use |
| --- | --- | --- |
| Standalone infrastructure | [Compose](https://github.com/sandbox-quantum/switch/blob/6e4ade5269d65ee38060a9f43b77c5e5b3be2f10/deploy/local/standalone-docker-compose.yml) | Layer `compose.yaml` on it using `--project-directory` so contexts resolve consistently |
| Mattermost/team/account/bridge setup | [setup.py](https://github.com/sandbox-quantum/switch/blob/6e4ade5269d65ee38060a9f43b77c5e5b3be2f10/deploy/shared_resources/setup.py) | Execute unchanged; includes gateway-cookie login and owner identity linking |
| Registration and heartbeat schemas | [schemas.py](https://github.com/sandbox-quantum/switch/blob/6e4ade5269d65ee38060a9f43b77c5e5b3be2f10/core/switch_core/bridges/agent/api/schemas.py) | `POST /agents` with registration key; agent API keys are separate credentials |
| SSE and media HTTP routes | [handlers.py](https://github.com/sandbox-quantum/switch/blob/6e4ade5269d65ee38060a9f43b77c5e5b3be2f10/core/switch_core/bridges/agent/api/handlers.py) | `GET /agents/{id}/events`, `POST .../connection/beat`, room-scoped attachment downloads |
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
    P->>P: Commit a new local preview version
    P->>S: Preview URL; publication requires exact-version consent
    H->>S: Natural-language revision / factual clarification
    S->>C: Start a new version with shared context
```

The web application provides version storage, photo sanitization, and a projection of the actual collaboration events. It cannot start AI generation or approve publication through a browser write API. No browser token is shipped. Model child processes receive a filtered environment without Switch, Mattermost, web-internal, or publishing credentials.

## Retry and recovery limits

Each process opens one stable connection ID per process lifetime, specifies its room at stream-open time, sends fenced heartbeats, and reconnects. On startup, reconnect, or `gap`, it reconciles durable room history using per-role processing receipts. Replaying a processed event cannot create another preview version. A job records its base revision and rejects stale commits. Simultaneous requests are refused visibly.

This is at-least-once infrastructure with a bounded MVP worker, not a transactional distributed workflow engine. A crash precisely between creating a document and recording its handoff can require a fresh human request; duplicate artifact names fail visibly. Jobs abandoned by a crash expire after 15 minutes. Restarting an upstream server, a worker, or the full local stack is part of the smoke/restart checks; no provider session is assumed to survive a failed model call.

One stack has one private travel room and one current book. Codex Editor receives up to eight sanitized image attachments for visual review; text posts remain the authority for travel events and dates. Multiple independent trips, automatic geolocation/identity inference, multi-tenant access, and a general-purpose agent planner are outside this implementation.
