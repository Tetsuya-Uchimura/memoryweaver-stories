# Verification record

## Pre-push source verification — November 6, 2026

- The current source passed all **77 Python tests** with native PDF dependencies and **22 desktop/mobile Chromium tests** after the automatic-map fallback fix. The browser run used `PLAYWRIGHT_CHANNEL=chrome npx playwright test tests/browser/maps.spec.js tests/browser/studio.spec.js --workers=1 --trace=off --output=.runtime/maps/pre-push-check`.
- All application JavaScript syntax checks, whitespace checks and distributable-file secret scanning passed. The source includes the English four-trip showcase, Santorini coastal design, obsolete-sample retirement and automatic street maps. Video production, original completed movies, new recordings and all generated media remain excluded from Git. Source publication does not authorize a public travel-book deployment.

## Automatic street maps — November 6, 2026

- Supersedes the button-based startup described in the earlier record below. Coordinate-equipped albums now load their map automatically in the local studio and future approved exports. Startup keeps the reader at the cover; it neither scrolls to the map nor requires **Load street map**. Hiding/restoring a map, photo navigation, offline coordinates and retry remain available. Name-only places make no tile requests.
- Desktop and mobile checks exercised all four isolated fictional books, automatic tile requests, origin-only referrers, photo selection, strict-CSP static exports and unchanged initial scroll position. An offline regression exposed Leaflet still accessing its map after its tile-load callback; deferring failed-map removal until the callback finishes resolved the JavaScript errors. The focused six-case desktop/mobile fallback and studio rerun passed, covering retry, photo/book switching, existing dialogs and saved-version links. Two location/export Python checks passed as well. Automated browser checks intercept all public tile requests, including existing studio/location tests.
- Visible Chrome loaded the real Kyoto street map without any button click: map state `ready`, 12 tiles already loaded at the check, initial `scrollY=0`, and the load button hidden. The screenshot remains local at ignored `.runtime/maps/kyoto-auto-street-map.png`.
- Rebuilt `web` and `publisher` only, with no re-seeding or new album editions. The catalog still has Kyoto v6, Paris v3 and New York v2; Santorini remains ungenerated in this running stack. README/privacy text reflects automatic third-party tile requests. No commit, push, publication approval, deployment or external upload was performed.

## Opt-in street maps — November 6, 2026

Historical verification of the earlier startup behavior; automatic loading above is the current behavior.

- Added a real OpenStreetMap basemap to the studio and future human-approved static exports, using locally bundled Leaflet 1.9.4. No API key, new Docker service or model generation is needed. Numbered pins show sourced location labels and matching local photographs. Photo/place controls select a precise stop, bring its pin forward and zoom in; unknown or name-only locations are never geocoded.
- No tile requests occur before **Load street map**. Automated browser tests substitute tile images and verify origin-only referrers, attribution, photo navigation, all four fictional destinations, single GPS locations, date-line bounds, escaped hostile names, rejection of external popup photo URLs, failure/retry, static-export CSP, reading mode and mobile width. Sample books and export fixtures are created in isolated temporary storage, not the running studio's databases; these rendering tests do not claim fresh live agent inference.
- **77 Python tests passed** with the documented Homebrew Pango library path, including actual PDF rendering, approval-bound metadata and export allowlist/escaping checks. **22 Chromium browser tests passed** in desktop and iPhone 13 viewports: `PLAYWRIGHT_CHANNEL=chrome npx playwright test tests/browser/maps.spec.js tests/browser/studio.spec.js --workers=1 --trace=off --output=.runtime/maps/verified`. This includes existing studio and saved-version link checks. Physical mobile devices remain untested.
- A separate visible Chrome check loaded the real Kyoto basemap successfully (15 visible tiles returned HTTP 200). Roads, terrain, attribution and five unique location pins were visually inspected. The local screenshot is in ignored `.runtime/maps/kyoto-real-street-map.png`; public-service tile downloads are not part of the automated suite.
- Rebuilt only `web` and `publisher` with `--no-deps`. The running catalog retained Kyoto LIVE v6, Paris REPLAY v3 and New York REPLAY v2. Santorini has no generated edition in this running stack; its new map rendering was tested with isolated fictional fixtures, without creating a live album or changing any sample conversation.
- Updated English setup/privacy documentation. PDFs retain coordinate/place links without downloading street tiles. Source checks and secret scanning passed; screenshots and video artifacts remain ignored. No Git commit, push, public-book approval, cloud deployment or external upload was performed. Actual Cloudflare deployment of the new map remains unverified.

## Expanded photographs and book art direction — November 5, 2026

- Expanded the four primary fictional fixtures to **six distinct licensed photographs each**: Kyoto has 9 source memories, Paris 8 and New York 8. Added Gion / Togetsu-kyo / a second temple view; Paris bridge / Montmartre / Tuileries / Notre-Dame; and DUMBO / Times Square / Bethesda Terrace / Grand Central. Metadata-free JPEGs and complete attribution/license records ship in Git.
- Native Console Claude → Codex → Publisher produced **Kyoto LIVE v4** with all 9 sources and 6 photos, through genuine Switch draft/review documents. The native smoke observer downloaded the real Mattermost cover/PDF and verified byte equality with the saved artifacts and HTTP PDF endpoint. The existing bamboo cover was preserved. Paris and New York refreshed sample books remain explicitly **REPLAY**.
- Web, PDF and sanitized exports use an edition-bound allowlisted design: Kyoto `quiet`, Paris `editorial`, New York `urban`. AI collaborators can select the recipe through Album JSON; missing recipes resolve from supplied destination/cited place names. Raw model CSS/HTML is rejected by the schema. Style changes invalidate the exact-version publication digest; older recipe-less editions use classic and previously delivered PDFs remain byte-stable.
- **71 Python tests passed**, including actual PDF rendering for all three new recipes, six distinct sourced photos per book, location/recipe snapshot and consent integrity, export verification, and existing delivery/privacy regressions. **8 desktop/mobile Chromium tests passed** with all six photographs loaded in each book, matching recipe attributes, local map interactions, no remote image/font/tile requests, no horizontal overflow, and retained legacy links.
- Upgraded the running Docker setup and seeded only missing posts through real Mattermost/Switch. Re-running the seed checks per-post receipts instead of skipping all additions after `seed:complete`. Publisher's asynchronous Switch → Mattermost delivery required the native smoke observer to wait for the actual post, rather than assume immediate bridge visibility after acceptance.
- **Fresh clone verified for this change:** commit `817f189` was cloned into an independent checkout; bootstrap fetched the official source pin, generated different credentials, and used project `memoryweaver-design-judge` with fresh PostgreSQL/Mattermost/data/auth volumes and ports 18000/18065/18787/55434. No developer/native authentication was copied. All three books contained exactly their fixture photos (6 each), 9/8/8 source memories, distinct recipe IDs and non-overlapping source IDs. Real Publisher posts had the correct trip/version links and byte-identical cover/PDF downloads. Re-seeding added no duplicates.
- The independent stack passed the full `scripts.smoke` regression: generation, cover edit, prose edit, prior versions, actual PDF delivery, resend recovery without duplicate publication posts, stale-consent rejection, contributor authorization and verified local export (12 allowlisted files). Cloud publishing stayed disabled. The test stack was stopped with volumes retained. The developer stack was restored/checked afterward: Kyoto LIVE v4, Paris REPLAY v3 and New York REPLAY v2 all retain six photos and verified Mattermost/HTTP artifact bytes; existing private retired pre-showcase LIVE v13 retains its seven sources/five photos.
- Updated the English README with photo counts, design behavior, explicit redesign instructions and the additive upgrade procedure. Cloud publication remains disabled; no GitHub/Cloudflare book publication or approval was performed.

## Locations and world-trip showcase — November 5, 2026

- **Three real private sample channels and separate books:** `kyoto-travel-journal` (6 English memories / 3 photos), `paris-travel-journal` (4 / 2), and `new-york-travel-journal` (4 / 2). Kyoto is the default; upgrades keep the previous retired pre-showcase root database, sources, media and v13 instead of relabeling them. A database backup was made before the upgrade.
- **Location provenance:** real JPEG EXIF GPS was exercised through the HTTP sanitizer using a synthetic GPS-equipped image; the saved location record retained the coordinates while the served JPEG contained no EXIF. Explicit place annotations, name-only locations, coordinate bounds, unknown places, source overrides and edition snapshots were checked. Stock sample pins are authored approximate landmarks, not claimed original camera positions.
- **Actual native Kyoto inference and edit:** authenticated Console Claude → Codex → Publisher produced **LIVE v2 and v3** through Switch. The v2 → v3 cover changed from `kyoto-gates` to `kyoto-bamboo`; chapter arrays were exactly equal and all six sources, three photos and their location snapshots were preserved. Mattermost PDF/cover bytes matched the saved artifacts and the HTTP PDF endpoint. Paris/New York initial previews are explicitly labeled **REPLAY**, not claimed live model output.
- **Fresh-clone Docker regression:** a local Git clone fetched the official source pin and used project `memoryweaver-world-judge-final`, separate fresh PostgreSQL/Mattermost/data/auth volumes, generated secrets different from the developer's, and separate ports (18000/18065/18787/55434). No legacy/private input or provider authentication was imported. All three rooms generated complete replay books through actual Switch handoffs. Each real Publisher post had the correct trip/version URL, cover/PDF group and byte hashes. Source IDs did not overlap between trips.
- The fresh environment then passed `scripts.smoke`: Kyoto generation, a real bamboo-cover edit, day-two prose edit, version preservation, real PDF delivery, resend recovery without duplicate posts/versions, stale-consent rejection, contributor authorization rejection and a verified allowlisted local export. **No cloud publication occurred.** The independent test stack was stopped afterward with volumes retained; the original developer stack remains running.
- Fresh testing exposed asynchronous sample intake and a second-reader connection interfering with worker delivery. The seed helper now uses the audited **connectionless `read_context(room_id=...)` / `get_room_detail` operations**, opens no worker SSE session, and waits for exact text and photo-byte acknowledgement before asking for generation. It stops visibly rather than knowingly generating an incomplete fixture.
- **67 Python tests passed**, including GPS extraction, location snapshots/consent, unused-location exclusion, namespace/version isolation, legacy URLs, active-trip binding checks, complete/non-interfering seed acknowledgement, and byte-stable delivered PDFs across location/template upgrades. **8 desktop/mobile browser tests passed**: the three English books, all loaded photos, location pins and links, local interactive sketch, no automatic external map requests, no horizontal overflow, and retained legacy completion links.

The fixtures and setup commands are in [README](../README.md). Seven resized, metadata-free Wikimedia photographs are shipped with [attribution/license links](PHOTO-CREDITS.md), so judges do not fetch images at startup. The primary screenshot now shows only the fictional Kyoto fixture. Real family images, generated private PDFs, runtime databases and credentials remain outside Git. Native setup on a second physical machine, physical mobile Safari/Android, arbitrary new trip creation and actual Cloudflare publication remain unverified or outside the current scope.

## Console-native verification — November 5, 2026

**Passed with real authenticated providers:** Switch Console **0.40.1**, the pinned Docker Switch core **0.31.0**, and the user's independently registered `mw-storyteller-claude` / `mw-editor-codex` agents. No host provider credentials were copied to Docker. Docker's original model workers remained idle in Console mode.

- Mattermost Collector requests produced native Claude drafts and native Codex reviews through real Switch documents and targeted handoffs. Publisher saved **LIVE v11, v12 and v13**. Each retained **7 source posts, 5 photographs and 4 chapters**, including an existing private user-uploaded photograph.
- The v12 → v13 request changed the cover from `sunset` to `coast`. The chapter arrays were **exactly equal**, verifying that this cover edit preserved the text, citations and photos. The known travel range remained October 12–14; the extra posted-only photo remained an explicitly undated photo note.
- For all three versions, the integration observer verified the actual Publisher bot identity, title, version URL and both Mattermost attachments. Downloaded PDF/cover bytes matched the saved artifacts; the application's PDF download matched too. Public approval/deployment state did not change.
- Initial live trials exposed a textual value in the ISO date field and a technical question about photo-note rendering. The final schema now constrains ISO dates, the role protocol explains the tested renderer behavior, and an Editor can ask Publisher a structured rendering question through Switch. Unapproved reviews preserve the preview and can resume; newer requests supersede pending clarification jobs.
- **50 Python tests passed**, including genuine native receipt flow, spoofed ID rejection, changed evidence/draft detection, citation/quote checks, wrong-job/draft rejection, corrected drafts, clarification/resumption/supersession, renderer replies, runtime configuration authentication and idled Docker inference. Existing PDF/delivery/publishing tests remain included. **4 desktop/mobile browser checks passed** against the saved live book.

Reproduction is documented in [Console setup](CONSOLE.md). `scripts/console_smoke.py` observes a requested native generation and can issue a real cover edit, checking receipts and attachment hashes without consenting to publication. Provider model availability and authentication remain account-specific. Native inference was exercised on this Mac; a fresh Console registration on a second physical machine has **not** been tested. The earlier fresh-clone Docker replay verification below remains a separate infrastructure check. Container-CLI live inference and actual Cloudflare deployment remain unverified.

The evidence contains personal input and is retained only in ignored local Docker/runtime storage. No private book, uploaded photo, account credential, generated PDF or new screenshot is included in this source change.

## Earlier replay/infrastructure verification

Verified on **November 5, 2026 (Asia/Tokyo)** on macOS / Apple Silicon, Docker Desktop Engine 29.1.3. Mattermost runs as the upstream-pinned amd64 image under emulation. Switch was built from official commit `6e4ade5269d65ee38060a9f43b77c5e5b3be2f10`.

## Completed

| Check | Result / evidence |
| --- | --- |
| Official Switch source builds | Core and official setup Dockerfiles built successfully |
| Mattermost automated setup | Fresh database, admin, traveler, team, bridge and owner identity link created by upstream setup |
| Project bootstrap | Four API-registered agents, actual Mattermost bot identities, private bridged room, sample asset metadata |
| CLI installation | Docker executes `codex-cli 0.166.0` and `Claude Code 2.1.309` |
| Real protocol compatibility | Operation discovery, connection-state parsing, fenced heartbeat generation, source-history pagination, media downloads, room-document creation/loading and targeted messages |
| Real sample generation | Six shuffled messages and four actual uploaded photographs from traveler and hana produced a three-chapter book through Switch |
| Real human revision | Mattermost sunset-cover request produced a new version; second-day tone request changed its prose while preserving the cover |
| Private artifact delivery | Actual Switch multipart upload produced one top-level Mattermost post from `mw-publisher` with title, version URL, cover JPEG and PDF; verified initial book and two edits (v6–v8), downloaded actual files, compared hashes to saved versions and the local PDF route |
| Real delivery reconciliation | A human `@mw-publisher resend PDF v3` in the independent stack recovered the accepted Switch attachment group; one completion post remained and no extra book version was generated |
| PDF appearance and Japanese fonts | Docker-rendered five-page sample PDF (941,486 bytes for development v8): Japanese narration/quotes extracted correctly; cover and chapter pages rendered and visually inspected |
| Attached-request regression | Fixed Collector dropping the entire instruction post, including its photograph. Reprocessed the original authoritative human request through the regular Collector → Switch document → Storyteller → Editor → Publisher path. Local v10 contains seven source posts and five photographs. Its actual Mattermost PDF was downloaded and matched to the six-page local version; request text is absent from prose/quotes, and the undated image is labeled with its posting date. Desktop/mobile checks loaded the added private JPEG successfully. No uploaded photograph was added to Git |
| Preservation | Earlier versions remained readable; source posts retained their actual author, date and photo references |
| Approval failure cases | Old-version command rejected; another real human contributor could not approve publication |
| Local approval/export | Exact current consent produced a nine-file sanitized static export; release verifier passed; no cloud calls |
| Full stop/start | `down` followed by `up` re-created services, retained six sources and version 5, preserved local-export state, and reconnected all four agents without duplicate versions |
| Independent Docker stack from GitHub clone | Cloned source commit `aeb5347` from GitHub into a clean directory, ran the standard `up`, fetched the audited Switch commit, and generated independent mode-0600 secrets; isolated project `memoryweaver-judge-20261105` used fresh PostgreSQL, Mattermost, book and AI-auth volumes. Bootstrap automatically created all four agents and a private bridged channel. Full smoke passed for v1–v3: generation, two edits, actual PDF/cover delivery, retry reconciliation, and consent checks. Cached image layers were reused; no developer data or account credentials were copied |
| Unit/contract checks | **36 passed**: image-plus-command collection in English/Japanese, caption and explicit capture-date preservation, WebP sanitization, repeated-ingestion deduplication, posted-date uncertainty in web/PDF; plus Japanese PDF text and metadata, version-bound artifact caching, private resource fetcher, durable delivery intent, retry and accepted-group recovery, multipart agent-key contract, versioned PDF download, safe preview URL, concurrent rejection isolation; plus chronological evidence, unknown references, verbatim quotes, photo-source correspondence, concurrent edits, stale commits, exact consent, byte-bound photo approval, export allowlist, HTML escaping, no unused-source export, unauthorized writes, EXIF removal, sender identity checks, model subprocess schema/argument handling and secret filtering, mocked GitHub subtree/status contract, public-repository rejection before writes, Cloudflare setup API contract, refusal to reconfigure existing projects, local-token file permissions, and redacted secret handling |
| GitHub source and CI | Source pushed to private `Tetsuya-Uchimura/memoryweaver-stories`, `main`; PDF-enabled Verify MemoryWeaver Actions run [41917486179](https://github.com/Tetsuya-Uchimura/memoryweaver-stories/actions/runs/41917486179) passed all 28 tests on Ubuntu with Japanese fonts; `production` environment created |
| Browser checks | **4 passed**: saved-version completion links, plus desktop and iPhone-13-sized Chromium viewports using installed Google Chrome; story, evidence dialog, inbox, activity, edit prompts, publication review, photo view, no horizontal overflow, no JS page errors |
| Source hygiene | Generated local secret values absent from distributable Git files; `.env`, `.runtime`, virtualenv and node_modules ignored |

The integration test is `scripts/smoke.py`; it refuses live AI or enabled cloud publishing. Unit tests exercise model harnesses with controlled subprocess substitutes and GitHub with an in-memory HTTP transport. They verify our adapter contracts, **not model access, output quality, or an actual cloud deployment**.

The standalone Playwright Chromium download stalled in this environment and was stopped. Tests successfully used an already installed Google Chrome with `PLAYWRIGHT_CHANNEL=chrome`. No provider keys or existing browser login profiles were imported. Tests run a separate temporary browser profile.

## Not yet verified

- **Container-CLI live generation** remains unverified; the authenticated Console-native path is now verified above. Exhaustive visual examination of every photo and creative quality are not guaranteed by schema/evidence checks. Inspect the generated book before recording a demo.
- **Actual approved-book commit → GitHub Actions → Cloudflare Pages deployment and URL callback.** The private repository and source CI are configured; the Publisher's scoped GitHub token, Cloudflare account/project, and production secrets are not yet supplied. `scripts/setup_publishing.py` prepares the optional publishing services; its unit checks use substituted provider responses. No production deployment or public URL is claimed.
- **A fresh clone on another physical machine.** A completely separate Docker project from a fresh GitHub clone passed on this Mac; independent Linux/Windows hardware and network conditions have not been tested.
- **Real iOS Safari, Android browsers, and accessibility assistive devices.** Mobile layout was tested in a Chromium device viewport, not on physical phones.
- **Crash at every instruction boundary, very large albums and long-running provider outages.** See the explicit MVP limits in the architecture and security documents.
- **Demo-video recording/upload and hackathon submission.** A detailed storyboard is provided in `docs/DEMO.md`; no external upload or submission was made.

## Re-run

```sh
# Apple Silicon with Homebrew Pango: prefix with DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
.venv/bin/python -m pytest -q
node --check app/static/app.js
python3 scripts/check_secrets.py
python3 scripts/dev.py compose config --quiet
python3 scripts/dev.py compose run --rm --no-deps -T bootstrap python -m scripts.smoke
PLAYWRIGHT_CHANNEL=chrome npm run test:browser
```

Use the README’s standard Chromium installation path if Chrome is not installed. The browser checks expect a generated replay sample. The smoke test makes new local versions and a local approved export; it does not publish externally.

## Official implementation references

- [Switch source pin and API audit](SWITCH.md).
- [Codex non-interactive execution](https://developers.openai.com/codex/noninteractive), [Codex authentication](https://developers.openai.com/codex/auth).
- [Claude Code programmatic execution](https://code.claude.com/docs/en/headless), [Claude Code authentication](https://code.claude.com/docs/en/authentication).
- [GitHub Git Trees API](https://docs.github.com/en/rest/git/trees), [Wrangler GitHub Action](https://github.com/cloudflare/wrangler-action), [Cloudflare Pages Direct Upload with CI](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/).
