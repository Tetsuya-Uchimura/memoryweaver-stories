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
- Uploaded images are decoded, resized, re-encoded as JPEG, and stripped of raw EXIF after valid GPS is extracted into a separate private location record. Supported image size is 20 MB and 40 megapixels. Non-image files are not imported into the book.
- Finished books and cover photographs are sent back into the same private Mattermost room automatically using Publisher's Switch media endpoint. This requested private delivery is separate from public GitHub/Cloudflare approval. PDFs include selected narration, quotations and photos; they are available to channel members and stored in local Docker volumes. Unused source posts are excluded. Rendering cannot fetch arbitrary network URLs or local files.
- Source and model strings are escaped before HTML rendering. Preview and static exports use restrictive content security policies and `nosniff` headers.

## What local-only does and does not mean

The default replay mode sends no model requests. **Live mode sends source text, contributor usernames, photo references, previous drafts, and editing instructions to the authenticated AI providers. Codex Editor also receives up to eight sanitized photograph attachments for visual review.** Refer to your provider’s account settings, retention policies, and terms before using sensitive memories. On-disk storage being local does not mean live inference is local.

The preview read API has no login. Any process/user that can reach this machine’s loopback ports can read the local book and original-source display. Do not expose this stack through a tunnel, a LAN bind, a public reverse proxy, or shared-host ingress without adding proper authentication and authorization. Docker administrators and local disk administrators are trusted and can inspect volumes.

The upstream Mattermost setup enables open server registration; we retain that official setup but use a private room. This is appropriate only inside the stated local boundary.

## Prompt injection and factual integrity

All source text, captions, and natural-language edits are treated as untrusted model input. Claude’s model call has tools and MCP disabled. Codex uses a read-only sandbox, disabled shell/unified-exec/app features, disabled web search, an empty MCP configuration, and ephemeral execution ignoring user/project policy configuration. Model subprocess environments exclude Switch, Mattermost, internal-web and publishing credentials. The model code does not interpret returned strings as shell commands, file paths, or network operations.

Typed schemas reject unexpected fields. Chapters require valid source references and photo references; a selected chapter photo must occur in its cited posts. Quotes must occur verbatim in their cited source. Codex reviews narration against the supplied evidence before a preview is committed. This does not prove every free-form sentence is true; the human reviews the result. Missing information is not a license to invent events.

The source collector preserves original text and explicit capture times. It does not infer a person’s identity, a place name or address from GPS, a relationship from a photograph, or unstated travel events. Multi-file posts are represented as source entries with attachments; upstream grouping may yield separate entries for multiple attachments. The sample uses one photo per post. Robust coalescing of upstream multi-file event batches is not yet implemented.

## Publication boundary

Only an authoritative human message, mapped through Switch’s server-generated join history and participant roster, from the configured traveler username can approve. Agent text and copied `MW_HANDOFF` strings from a human cannot impersonate an agent handoff. The current version, public-book digest, photo byte hashes, and explicit consent phrase must match, with no edit in progress.

The export uses an explicit file allowlist. It never recursively copies a repository, source history, or upload directory. GitHub writes are limited to `published/current` and use a non-force reference update. A private repository is required. Cloudflare Pages is public: publication is intentional disclosure of the approved book and photos.

The local bootstrap receives administrative credentials to initialize Mattermost and Switch. The web and regular agent services receive only the settings needed for their roles. Bootstrap and sample seeding run as short-lived trusted tooling. Do not place arbitrary code in this repository or authenticate AI clients against an untrusted checkout.

Backups, encrypted storage, automatic retention/deletion, production authentication, and strong cryptographic attestation of human consent are not implemented. Preserve volumes if you need the memories; `down` retains them. Never use `down --volumes` unless you intend to delete local data and provider sessions.


## Location data and multiple trips

Explicit `[Location: Name | latitude,longitude]` annotations and valid EXIF GPS are the only automatic location inputs. Raw EXIF is removed from the served JPEG. Name-only locations are not geocoded and no reverse geocoding runs. Stock fixtures use separate, labeled approximate fictional landmark pins rather than original photographer GPS. Unknown locations stay unknown.

Albums with supplied coordinates automatically load street maps when opened, in both the local studio and approved static exports. This makes direct browser requests to `https://tile.openstreetmap.org/{z}/{x}/{y}.png` for the displayed area without a button click. The provider receives the viewer's IP, map area and site origin; tile images explicitly use `referrerPolicy: origin` so trip IDs and version URLs are withheld. Photos and messages remain on the studio or approved export origin. Leaflet 1.9.4 and its assets are bundled locally, no geocoding/API key/proxy is used, and the CSP allows only this additional image host (not third-party scripts or connections). **Hide street map** removes its Leaflet instance for the current view; reopening the album or switching editions loads its map again. Failed tile loads restore the studio's coordinate sketch and offer a retry. Static exports retain the coordinate/place list. Name-only locations do not trigger tile requests. Open map links independently send the selected place/coordinates when opened. PDFs never fetch remote tiles.

Approved exports include the same automatic map runtime from an explicit filename allowlist and approved photo references only. Map metadata uses an escaped JSON data attribute; popup text is inserted with DOM `textContent`, and popup image URLs are restricted to local photo paths. Raw source IDs and conversation text are not added to map metadata. Browser tests intercept tile requests with test images rather than downloading tiles from the public service.

Locations are snapshotted with each edition and included in its public-book consent digest. The publication review explains that coordinates will be included in an approved export. Unused source locations are excluded. Each catalog trip uses a separate SQLite file/media directory; the old root database remains the legacy book after an upgrade. This is room/book separation within one local studio, not a multi-tenant authorization system. All endpoints remain loopback-only in the default Docker setup.
