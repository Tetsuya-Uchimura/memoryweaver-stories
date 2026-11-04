# Optional GitHub → GitHub Actions → Cloudflare Pages publishing

Local judging needs none of these accounts. Do not configure publishing until you have reviewed the book and understand what will be public.

## Prepare your own developer environment

1. Create a **private GitHub repository** containing the MemoryWeaver code, `.github/workflows/publish.yml`, and `scripts/verify_release.py`. Its default publication branch is `main`. Keep `.env`, `.runtime`, Docker volumes, and actual personal photos out of Git. A private repository is enforced by Publisher.
2. Create a **Cloudflare Pages Direct Upload** project with production branch `main`. Use the [official Direct Upload CI instructions](https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/). Do not configure a second automatic Git integration for the same project.
3. In the repository, create the GitHub **production** environment. Add `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` as environment secrets. The API token needs Cloudflare Pages edit access only on your account. Set `CLOUDFLARE_PAGES_PROJECT` as an environment variable. You may additionally require a human reviewer for this environment.
4. Create a fine-grained GitHub token scoped only to this private repository. Publisher needs **Contents: read/write** and **Commit statuses: read**. It does not need account-wide access or workflow-edit permission. Use a PAT or GitHub App token; the built-in Actions token usually does not trigger a subsequent push workflow.
5. In your local, gitignored `.env`, add:

```dotenv
PUBLISH_ENABLED=true
PUBLISH_GITHUB_REPOSITORY=your-account/your-private-repository
PUBLISH_GITHUB_BRANCH=main
PUBLISH_GITHUB_TOKEN=your-locally-stored-scoped-token
```

Do not paste tokens into Mattermost or the book UI. Do not commit them. Run `python3 scripts/dev.py up` to recreate services with the updated configuration. Only the Publisher receives the GitHub token; model processes receive no publishing secrets. Cloudflare credentials live in GitHub, not the application.

## Approve a concrete book

Review the current local book’s text, verbatim quotations, and every selected photograph. Click **Review publication**. The command includes the current version and a digest of the public book and selected photo bytes. Send that exact command yourself from the configured traveler account in Mattermost:

```text
PUBLISH v3 <your-current-digest> I CONSENT TO PUBLIC PHOTOS AND TEXT
```

Ordinary requests such as “looks good”, “publish it”, agent messages, another person’s consent, an old command, or a command sent while an edit is running cannot authorize publication. The provider models never approve or execute publication.

Publisher creates an allowlisted static export, uploads Git blobs, creates an export subtree, creates a commit preserving the rest of the repository, and updates the branch **without force**. The resulting push triggers the workflow only for `published/current/**`. It replaces that subtree so unused files are absent from the current export.

Actions verifies the consent marker, canonical digest, exact file allowlist, photo hashes, and file hashes before deploying. It deploys only `published/current`, then writes a `memoryweaver/cloudflare` commit status whose target is Wrangler’s actual Pages URL. Publisher polls that exact commit and posts the returned HTTPS `*.pages.dev` URL in the original Mattermost conversation. It never fabricates a deployment address.

## What leaves the machine

- The approved static HTML/CSS and public book JSON.
- Only photographs selected for this book, with metadata removed.
- Applicable stock-photo credits and licenses.
- An approval manifest containing hashes, version, time, and a hash of the approver ID.

No raw Mattermost transcript, unused photograph, local database, Switch registration key, provider session, `.env`, or project workspace is copied into the export. Selected prose and quotations may contain personal information: approving them explicitly makes them public.

## Revisions, retries, and removal

Request an edit in Mattermost, review the new local version, then consent to that new version. The local edit alone does not update a public website. The latest local draft may therefore differ from the last published edition.

A successful duplicate approval returns the existing URL. A publication marked in progress is not started again. A failed workflow is visible; inspect it before retrying the same exact approval. After the 10-minute polling window, inspect GitHub Actions; the public deployment may finish later. A retry after a timeout currently creates a fresh commit and workflow, rather than reconciling a previous in-flight workflow. This MVP limitation is explicit; wait for the previous workflow to finish first.

GitHub commit history and Cloudflare deployment history can retain previously published material. Removing a photo from a new export does not retract those historical copies. Use only licensed sample material for a hackathon demonstration. If you need deletion, remove the Pages project/deployments and handle GitHub history separately with the appropriate provider tools.

The checksum manifest verifies consistency, not a cryptographic human signature. GitHub repository writers and production-environment administrators remain trusted. Protect the branch and the production environment if other people can push code.

## Local export without cloud accounts

With `PUBLISH_ENABLED=false`, the same approval creates `/data/exports/vN` in the `memorydata` Docker volume and posts that location in Mattermost. Nothing reaches GitHub or Cloudflare. To inspect an approved export locally:

```sh
python3 scripts/dev.py compose cp publisher:/data/exports/v3 .runtime/export-v3
.venv/bin/python scripts/verify_release.py .runtime/export-v3
```

Replace `v3` with the actual approved version. The artifact is intentionally gitignored. Local judging does not require this approval step; generation and editing work without it.
