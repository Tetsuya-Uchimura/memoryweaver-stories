# A three-minute demo

Record a **live-AI** run for the hackathon submission when you have authenticated both providers. Keep the Replay Demo clearly labeled if you also show it for reproducibility. Use only the bundled fictional memories and licensed illustrative photos. Do not record passwords, device codes, tokens, browser account pages, `.env`, or real family content.

## Before recording

1. Start the stack with `python3 scripts/dev.py up`.
2. Follow [Console setup](CONSOLE.md) to authenticate/register/bind the native providers, or use the documented container-CLI live mode.
3. Open Mattermost at the private `okinawa-memories` channel and MemoryWeaver at `http://localhost:8787` side by side. Sign in before recording; close the credentials terminal.
4. If this stack already has sample data, `seed` will not duplicate it. A completely fresh judging installation starts with no memories and no book. For repeated filming, explain that you are regenerating the existing sample.
5. If showing actual cloud publication, configure the optional private repository and production environment beforehand. Demonstrate only after reviewing the exact sample version. No public deployment is necessary to show the local creative workflow.

## Storyboard

| Time | On screen | Narration / action |
| --- | --- | --- |
| 0:00–0:20 | Scattered posts in Mattermost | “These are the things we keep after a trip. Photos, small observations, words from different people. They arrive out of order.” Run `python3 scripts/dev.py seed` off-screen or type/post a sample naturally. |
| 0:20–0:35 | Mattermost | Send `@mw-collector 今回の沖縄旅行をアルバムにして`. “We ask our teammates to make something we can return to.” |
| 0:35–1:05 | Room thread and weaving-room feed | Show the four real bot identities. Collector shares evidence; Claude writes; Codex reviews. Show `MW_CONSOLE` → `MW_DRAFT` → `MW_REVIEW` (or container mode’s `MW_HANDOFF`) document references and the corresponding Switch room document in the admin UI if convenient. Explain that recipients load their work from Switch. Live inference latency varies; edit waiting time honestly. |
| 1:05–1:40 | Publisher completion post, then the book | Show the title, version-specific URL, cover preview and actual PDF attachment in the same Mattermost channel. Download/open the PDF, then follow the album link. Scroll through the chapters and open an original-memory citation. |
| 1:40–2:15 | Mattermost and book | Ask `@mw-collector 表紙を夕日の写真に変更して`. Receive an updated completion post, sunset cover preview and PDF. Old posts still link to their original versions. Ask for a more heartfelt second day if time allows. |
| 2:15–2:40 | Publication review | “Nothing has been published. We choose exactly what leaves our studio.” Show the version, photos, and consent command. With cloud disabled, approving the sample produces only a local export. With cloud enabled and explicit approval, show the real Actions run and the returned Pages URL. |
| 2:40–3:00 | README quick start | “Clone, Docker, your own AI sign-ins. No dependency on my Mattermost workspace or publishing accounts.” End on the book and the tagline. |

## Judges’ short path

```sh
python3 scripts/dev.py up
python3 scripts/dev.py seed --generate
python3 scripts/dev.py credentials
```

This exercises real Switch with labeled replay rendering. Then authenticate providers and switch to live mode to assess AI quality. The README separates both modes. The complete setup and integration smoke check are documented there.

## Submission checklist

- Repository URL and English README with source pin and setup commands.
- Actual demo video URL, showing Switch’s central role and human revision.
- Accurate verification record, including whether the recorded run was live or replay.
- Actual Pages URL only if a human-approved cloud deployment was completed.
- License credits for bundled photography.
- No credentials, private runtime data, personal family images, or provider-auth screenshots in the submission.

The repository supplies the storyboard and working sample; it does not fabricate a video upload, an external repository URL, or a successful production deployment.
