# Tapsroute Social Studio

A free-first, repository-backed social publishing starter for Tapsroute. The static GitHub Pages dashboard reads `data/dashboard.json`; Python workers and GitHub Actions update versioned JSON in the repository. Credentials stay in GitHub Actions secrets. The system is **not operationally connected to Meta or an AI model until the owner configures accounts and credentials**.

## Current implementation status

| Capability | Status |
|---|---|
| Responsive static dashboard and repository data | Implemented; deploy Pages from the default branch root and run Dashboard data refresh |
| Daily generation limit and IST calendar | Implemented with cross-process file lock and atomic JSON writes; GitHub workflow concurrency serializes repository writes |
| AI text | Optional local Ollama adapter implemented; model/runtime and secure reachability from Actions are owner prerequisites |
| AI image generation | Not implemented in the hosted worker. The worker can reuse only an owner-approved destination-matched AI image declared in `data/image-library.json`; otherwise the post is blocked |
| Human approval | GitHub `workflow_dispatch` approval/rejection workflow; requires repo write permission. Material edits must increment `content_version` and return the post to pending approval |
| Due-post scheduler | Implemented at 15-minute cadence; cron can be delayed by GitHub |
| Meta publishing | Official Graph API photo/feed and Instagram image feed sequence implemented, but **untested against owner accounts**. TEST_MODE defaults on |
| Retries and reconciliation | Partial: transient/permanent classification is exposed, retry count is stored, but automatic retry/backoff, timeout reconciliation, dead-letter controls, carousel, and token refresh are not implemented; failed posts require manual intervention |
| Analytics | Only platform IDs/status timestamps are recorded. Insights ingestion is not implemented |
| Dependency lock | No third-party runtime dependencies; `requirements.txt` documents standard-library-only runtime |

No integration is represented as connected until an owner configures and verifies it. The included Jaipur item is synthetic sample content, clearly marked `sample: true`, and is not approval-ready because it has no image.

## Tree

```text
.
├── .github/workflows/        # generation, review, due scheduler and dashboard refresh
├── assets/                   # dashboard styles and data reader
├── config/settings.json      # public, non-secret operating defaults
├── data/state.json           # versioned posts, generation counter and event log
├── data/sample_posts.json    # synthetic example; not active state
├── index.html                # GitHub Pages dashboard
├── src/tapsroute/core.py     # atomic JSON storage, limits, validation and approval
├── src/tapsroute/providers.py# local Ollama + explicit image import boundary
├── src/tapsroute/meta.py    # official Graph API adapter
├── src/tapsroute/cli.py     # workflow commands
└── tests/                    # isolated unit tests; no real account calls
```

## Local use

Requirements: Python 3.12 or newer. Runtime has no third-party dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
export PYTHONPATH=src
python -m unittest discover -s tests -v
```

Install Ollama and a model on the owner's computer (for example `ollama pull qwen2.5:3b`, subject to the model's own license and hardware needs), start Ollama, then run:

```bash
PYTHONPATH=src python -m tapsroute.cli generate --count 1 --destination Jaipur --language English
```

The worker reserves daily allowance before invoking the model. A provider failure does not refund that reservation; this conservative rule prevents concurrent runs and retries from over-consuming the cap. The GitHub workflow commits the reservation even if provider execution fails. The counter is one entry per `Asia/Kolkata` date and cannot exceed 12 even if settings are raised. Set a lower value in `config/settings.json` to lower the cap.

Generation currently requires an Ollama service reachable from the worker. GitHub-hosted runners do not have GPUs or access to a laptop's localhost. For a hosted manual run, set the GitHub Actions secret `OLLAMA_URL` to an owner-managed, securely exposed Ollama endpoint and a repository variable `OLLAMA_MODEL`; never expose an unauthenticated public Ollama port. This project does not provide a tunnel or service. If you do not have a secure endpoint, run content locally and import it through repository changes; the GitHub generation workflow cannot reach a local-only Ollama service.

The **Generate content** workflow defaults to `dry_run: true`. It creates a clearly marked synthetic post, updates the durable IST counter and does not call Ollama. It still requires an approved, destination-matched image library item before it can leave the blocked state. Set `dry_run: false` only when the secure Ollama prerequisite is in place.

## AI images

The project does not bundle image weights or run image generation on Actions. Generate an image with a locally run open-source image model under its license, then place the original and final branded AI image under `images/`. Add an entry to `data/image-library.json` only after validating its destination, categories, model, prompt, original/final asset paths and public URL. The fallback accepts entries only when `validated_for_destination` is true, the destination matches exactly and a model identifier plus image location are present. Do not infer publicly accessible image URLs from local paths. The `public_image_url` adapter returns a Pages URL only when `PUBLIC_PAGES_CONFIRMED=true` and a repository is configured; the owner must independently verify that URL from outside GitHub. For Instagram, set `image_url` to a verified public HTTPS URL before approval or the post is blocked. GitHub Pages is public; never publish sensitive assets. Check current GitHub repository and Pages limits before adding large image libraries.

## GitHub deployment

1. Push this folder to a GitHub repository. In **Settings → Actions → General**, allow GitHub Actions to create and approve pull requests is not needed; set workflow permissions to **Read and write permissions** so these trusted workflows can commit JSON. Restrict who has write access; dispatch workflows are privileged actions.
2. In **Settings → Pages**, deploy from the default branch, `/ (root)`. The dashboard page URL is shown by GitHub Pages.
3. Run **Dashboard data refresh** from Actions once. It builds `data/dashboard.json` from `state.json` and settings. Subsequent scheduler, approval and generation runs refresh it.
4. Set repository variable `TAPSROUTE_TEST_MODE` to `true` (default behavior) until all setup and tests are complete. Set it to `false` only when intentional real publishing is approved and credentials/permissions have been verified. Also set `META_API_VERSION`, `META_PAGE_ID`, and `META_IG_USER_ID` as repository variables and `META_PAGE_ACCESS_TOKEN` as a secret. Never put tokens in JSON or frontend code.
5. Add `OLLAMA_URL` as a secret and `OLLAMA_MODEL` as a variable only if an owner-managed endpoint is securely reachable by Actions. Consider its network and data exposure before doing this.

### Meta setup and limitations

Create a Meta developer app, link a Facebook Page and Instagram professional account, and obtain a Page access token with only the permissions required by the currently approved Meta app/review and publishing use case. Account eligibility, app mode, permission names, token lifetime, API version availability and rate limits can change; verify the current official Meta documentation and test with a private test Page before enabling production. Required secrets/variables are listed above. The adapter accepts single image feed posts; it does not support carousels, Stories, Reels, comments, insights, or token refresh. The code has not been tested with live Meta credentials. Instagram media publishing requires Meta's supported account configuration and a reachable public HTTPS image. Errors redact response bodies and tokens. Test mode prevents all calls.

The configured default Graph version is a placeholder setting, not a claim that this version is currently supported for your app. Set the version supported by the app after checking Meta documentation.

## Review and scheduled operations

New posts begin `PENDING_APPROVAL`. A suitable image is mandatory. Open the Actions tab and run **Review a social post** with the post ID, approve/reject decision, and selected platform list. Approval records actor and timestamp; publishing rechecks approval and content version. The dashboard is read-only and does not hold a GitHub token. Editing a caption/image after approval must increment `content_version`, clear approval, and reset status to `PENDING_APPROVAL`.

The publishing workflow checks due items hourly (GitHub cron may start later). UTC cron is used; user schedule values and displays are IST. If a platform succeeds while another fails, status is partial and the published platform ID is retained. Automatic retry/backoff and timeout reconciliation are not implemented yet: manually reconcile Meta before retrying any ambiguous timeout to avoid duplicates. This limitation means failed publishing is not fully self-healing.

## Settings and branding

`config/settings.json` contains editable daily cap (maximum 12), supported language list, destinations, posting times, platforms, retry limit, approval mode, brand details and provider identifiers. Keep the Tapsroute details as supplied: https://tapsroute.com, +91 8450-98-4534, customer.experience@tapsroute.com. No Tapsroute logo was included in the initial workspace; configure `brand.logo_path` after adding the actual approved logo. Do not invent offers, package prices, hotel bookings or company credentials. Sample itinerary data is synthetic and requires human verification before use.

## Secrets and security checklist

- Never add access tokens to repository files, frontend source, artifacts, logs, image metadata or error messages.
- Use repository secrets only in protected workflows; keep write access limited to trusted maintainers.
- Do not grant secrets to untrusted pull-request workflows. These workflows use `workflow_dispatch` and do not execute PR code.
- Keep `TEST_MODE=true` by default. Exercise the dry-run/unit tests before setting false.
- Verify public image access, image destination match, caption facts, schedule, platform and approval before real publishing.
- The JSON state has no server-side identity/ACL; repository write permissions are the security boundary. Public Pages data must contain no private information.

## Troubleshooting

- **Ollama connection failure:** generation stops with a redacted actionable error; run Ollama locally or configure a secure reachable endpoint. The reservation remains counted for that IST day.
- **Post blocked:** add a suitable AI-generated destination-matched image and verified public HTTPS URL for Instagram; then submit for fresh approval.
- **Actions cannot push:** enable workflow read/write repository permissions and ensure branch protection allows the bot or use an approved PR-based state writer.
- **Meta permission or token error:** keep test mode on, verify app/account eligibility and token scopes in Meta developer tools; token refresh is not implemented.
- **Pages has stale data:** run Dashboard data refresh and confirm Pages is publishing the default branch root.
- **Duplicate concern after timeout:** check Page/Instagram media history manually before retry; automatic reconciliation is not implemented.

## Automated tests

Run `PYTHONPATH=src python -m unittest discover -s tests -v`. Tests use temporary files and mocked/dry-run conditions; they do not contact Meta or publish anything. Coverage includes the cap, concurrent workers, IST midnight, schedule handling, approval versioning, image requirement, language/price validation and dry-run publishing. Comprehensive testing of retry backoff, token expiry, Graph API throttling, real endpoint responses and live account reconciliation remains NOT IMPLEMENTED.

## Cost and free-tier caveats

This repository uses no paid API and no external database. GitHub Pages/Actions availability and quotas depend on the owner's plan, repository visibility, usage and current GitHub terms; verify applicable limits. Local model inference uses owner hardware and electricity. Meta developer access and publishing permissions depend on Meta eligibility and app review. No free provider is assumed unlimited or permanently available.
