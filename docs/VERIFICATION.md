# Verification record

Verified on **November 4, 2026 (Asia/Tokyo)** on macOS / Apple Silicon, Docker Desktop Engine 29.1.3. Mattermost runs as the upstream-pinned amd64 image under emulation. Switch was built from official commit `6e4ade5269d65ee38060a9f43b77c5e5b3be2f10`.

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
| Preservation | Earlier versions remained readable; source posts retained their actual author, date and photo references |
| Approval failure cases | Old-version command rejected; another real human contributor could not approve publication |
| Local approval/export | Exact current consent produced a nine-file sanitized static export; release verifier passed; no cloud calls |
| Full stop/start | `down` followed by `up` re-created services, retained six sources and version 5, preserved local-export state, and reconnected all four agents without duplicate versions |
| Unit/contract checks | **14 passed**: chronological evidence, unknown references, verbatim quotes, photo-source correspondence, concurrent edits, stale commits, exact consent, byte-bound photo approval, export allowlist, HTML escaping, no unused-source export, unauthorized writes, EXIF removal, sender identity checks, model subprocess schema/argument handling and secret filtering, mocked GitHub subtree/status contract, public-repository rejection before writes |
| Browser checks | **2 passed**: desktop and iPhone-13-sized Chromium viewports using installed Google Chrome; story, evidence dialog, inbox, activity, edit prompts, publication review, photo view, no horizontal overflow, no JS page errors |
| Source hygiene | Generated local secret values absent from distributable Git files; `.env`, `.runtime`, virtualenv and node_modules ignored |

The integration test is `scripts/smoke.py`; it refuses live AI or enabled cloud publishing. Unit tests exercise model harnesses with controlled subprocess substitutes and GitHub with an in-memory HTTP transport. They verify our adapter contracts, **not model access, output quality, or an actual cloud deployment**.

The standalone Playwright Chromium download stalled in this environment and was stopped. Tests successfully used an already installed Google Chrome with `PLAYWRIGHT_CHANNEL=chrome`. No provider keys or existing browser login profiles were imported. Tests run a separate temporary browser profile.

## Not yet verified

- **Authenticated live Claude Code → Codex generation**, model image review, account-specific model access, and creative quality. The container sign-in checks reported `loggedIn: false` / `Not logged in`. Complete the two documented human authentication flows, set `AI_MODE=live`, regenerate the sample, and inspect every result before recording a live-AI demo.
- **Actual private GitHub commit → GitHub Actions → Cloudflare Pages deployment and URL callback.** No publication repository, scoped GitHub token, Cloudflare account/project, or production secrets were supplied. The implementation and workflow are present; no production deployment or public URL is claimed.
- **A fresh clone on another physical machine.** This machine verified the initial fresh service setup and subsequent full restarts, not independent Linux/Windows hardware or network conditions.
- **Real iOS Safari, Android browsers, and accessibility assistive devices.** Mobile layout was tested in a Chromium device viewport, not on physical phones.
- **Crash at every instruction boundary, very large albums, multi-file batch coalescing, and long-running provider outages.** See the explicit MVP limits in the architecture and security documents.
- **Demo-video recording/upload and hackathon submission.** A detailed storyboard is provided in `docs/DEMO.md`; no external upload or submission was made.

## Re-run

```sh
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
