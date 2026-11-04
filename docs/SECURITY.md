# Privacy and security boundaries

MemoryWeaver is a **single-user, loopback-only development studio** with a private Mattermost collaboration channel. It is not a production-authenticated photo hosting service.

## Defaults

- Fresh random local passwords and secrets; `.env` is created with mode 0600 and ignored by Git and Docker build context.
- Upstream Switch uses a restricted runtime database role separate from its schema owner. We retain the official initialization and security checks.
- Mattermost, Switch, database, and preview ports bind to `127.0.0.1`.
- The travel room is private in both Switch and Mattermost.
- Actual images, transcripts, app versions, agent API keys, and AI auth live in local Docker volumes, never source control.
- Switch telemetry and third-party avatar generation are disabled in this stack.
- Browser writes require an internal bearer key unavailable to the browser. Editing and publication intent enter through Mattermost instead.
- Uploaded images are decoded, resized, re-encoded as JPEG, and stripped of EXIF/GPS. Supported image size is 20 MB and 40 megapixels. Non-image files are not imported into the book.
- Source and model strings are escaped before HTML rendering. Preview and static exports use restrictive content security policies and `nosniff` headers.

## What local-only does and does not mean

The default replay mode sends no model requests. **Live mode sends source text, contributor usernames, photo references, previous drafts, and editing instructions to the authenticated AI providers. Codex Editor also receives up to eight sanitized photograph attachments for visual review.** Refer to your provider’s account settings, retention policies, and terms before using sensitive memories. On-disk storage being local does not mean live inference is local.

The preview read API has no login. Any process/user that can reach this machine’s loopback ports can read the local book and original-source display. Do not expose this stack through a tunnel, a LAN bind, a public reverse proxy, or shared-host ingress without adding proper authentication and authorization. Docker administrators and local disk administrators are trusted and can inspect volumes.

The upstream Mattermost setup enables open server registration; we retain that official setup but use a private room. This is appropriate only inside the stated local boundary.

## Prompt injection and factual integrity

All source text, captions, and natural-language edits are treated as untrusted model input. Claude’s model call has tools and MCP disabled. Codex uses a read-only sandbox, disabled shell/unified-exec/app features, disabled web search, an empty MCP configuration, and ephemeral execution ignoring user/project policy configuration. Model subprocess environments exclude Switch, Mattermost, internal-web and publishing credentials. The model code does not interpret returned strings as shell commands, file paths, or network operations.

Typed schemas reject unexpected fields. Chapters require valid source references and photo references; a selected chapter photo must occur in its cited posts. Quotes must occur verbatim in their cited source. Codex reviews narration against the supplied evidence before a preview is committed. This does not prove every free-form sentence is true; the human reviews the result. Missing information is not a license to invent events.

The source collector preserves original text and explicit capture times. It does not infer a person’s identity, a location from GPS, a relationship from a photograph, or unstated travel events. Multi-file posts are represented as source entries with attachments; upstream grouping may yield separate entries for multiple attachments. The sample uses one photo per post. Robust coalescing of upstream multi-file event batches is not yet implemented.

## Publication boundary

Only an authoritative human message, mapped through Switch’s server-generated join history and participant roster, from the configured traveler username can approve. Agent text and copied `MW_HANDOFF` strings from a human cannot impersonate an agent handoff. The current version, public-book digest, photo byte hashes, and explicit consent phrase must match, with no edit in progress.

The export uses an explicit file allowlist. It never recursively copies a repository, source history, or upload directory. GitHub writes are limited to `published/current` and use a non-force reference update. A private repository is required. Cloudflare Pages is public: publication is intentional disclosure of the approved book and photos.

The local bootstrap receives administrative credentials to initialize Mattermost and Switch. The web and regular agent services receive only the settings needed for their roles. Bootstrap and sample seeding run as short-lived trusted tooling. Do not place arbitrary code in this repository or authenticate AI clients against an untrusted checkout.

Backups, encrypted storage, automatic retention/deletion, production authentication, and strong cryptographic attestation of human consent are not implemented. Preserve volumes if you need the memories; `down` retains them. Never use `down --volumes` unless you intend to delete local data and provider sessions.
