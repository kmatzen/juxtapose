# Juxtapose

A config-driven web application for running A/B evaluation studies. Define your entire survey -- demographics, stimuli, evaluation questions, and tutorial -- in a single YAML file. No code changes needed.

Built for research teams who need to collect human judgments on generated images with proper randomization, progress tracking, and data export.

## Features

- **Config-driven** -- one YAML file defines demographics, inputs, outputs, questions, and tutorial
- **A/B randomization** -- method positions randomized per trial to prevent bias
- **Multiple question types** -- A/B preference with confidence, Likert scales, free text, multiple choice
- **Conditional questions** -- hide questions when optional inputs are absent
- **Interactive tutorial** -- configurable walkthrough before the real survey
- **Progress tracking** -- participants can resume where they left off
- **Admin dashboard** -- real-time stats, per-question method preferences, CSV export
- **Consent management** -- configurable consent checkbox and privacy policy link
- **Security** -- CSRF protection, rate limiting, session management, audit logging

## Quick Start

```bash
pip install .
APP_ENV=dev DEV_MODE=true python -m src.survey.app
```

Open http://localhost:5000. Dev mode auto-fills forms, limits to 3 trials, and bypasses referral codes.
`APP_ENV` has no default: the app refuses to start without it, because it decides which security
gates are on. The dev database is written to `$TMPDIR/juxtapose-dev/survey.db`, not the checkout.

Example survey data is in the [`examples/`](examples/) directory.

## How It Works

1. Define your survey in `survey_config.yaml`
2. Prepare a tab-separated data file with one row per trial
3. Run the server
4. Share the URL with participants
5. Export results as CSV from the admin dashboard

## Configuration

Everything lives in [`survey_config.yaml`](survey_config.yaml). The included file is a complete working example for an image generation evaluation study.

### Survey Settings

```yaml
survey:
  title: "Your Study Title"
  description: "Introductory text shown on the demographics page."
  contact_email: "you@example.com"
  pairs_per_user: 30
  dev_pairs: 3
  consent_text: "I consent to the collection of my responses for research."
  privacy_policy_url: "https://example.com/privacy"
```

### Demographics

Fields shown before the main survey. The first `email` field is used for retake detection.

```yaml
demographics:
  - name: email
    type: email
    label: "Email Address"
    required: true
  - name: occupation
    type: select
    label: "Occupation"
    required: true
    options:
      - { value: "researcher", label: "Researcher" }
      - { value: "engineer", label: "Engineer" }
```

Types: `email`, `text`, `number`, `select`, `checkbox`, `radio`, `textarea`

### Data File

Tab-separated, one row per trial. Column order must match `data.columns`:

```yaml
data:
  file: "image_pairs.txt"
  columns: [prompt, method_a, method_b, image_a_url, image_b_url, mask_url, identity_urls]
```

### Inputs

Shared context shown for each trial. Optional inputs are hidden when their column value is empty.

| Type | Description |
|------|-------------|
| `image` | Single image, click to enlarge |
| `image_gallery` | Row of images from comma-separated URLs, or one stacked image sliced into a row |

An input named `prompt` with type `text` is not a widget: it enables the prompt box that shows the trial's `prompt` column. The config is the only switch for it.

Every input names the `data.columns` entry it reads with `column`. An input with no `column`, or one naming a column the data file does not carry, is refused at boot: the widget would have nothing to show, and a study that collects nothing is not worth running.

### Outputs

Per-method results shown as an A/B comparison. Position is randomized per trial.

| Type | Description |
|------|-------------|
| `image` | Side-by-side images, click to enlarge |

Every output names both of its columns, `column_a` and `column_b`, and each must be in `data.columns`. An output with only one of them is refused at boot.

### Questions

Evaluation criteria per trial. Rendered in order with progressive scroll navigation.

| Type | Description | Form fields |
|------|-------------|-------------|
| `ab_preference` | A/B/Equal choice with optional confidence scale | `{name}_choice`, `{name}_confidence` |
| `likert` | Numeric scale (configurable range) | `{name}_value` |
| `free_text` | Open text response | `{name}_text` |
| `multiple_choice` | Single selection from options list | `{name}_value` |

Every question needs a `type` from the table above; a question without one is refused at boot.

```yaml
questions:
  - name: image_quality
    type: ab_preference
    label: "Which image looks better?"
    confidence: true
    required: true
  - name: mask_adherence
    type: ab_preference
    label: "Which image follows the mask better?"
    depends_on: mask        # hidden when mask input has no data
```

### Tutorial

Interactive walkthrough shown after demographics. Steps are configurable, and the special `auto_questions` marker generates one step per question.

```yaml
tutorial:
  enabled: true
  steps:
    - title: "Before You Begin"
      text: "Let's walk through how this survey works."
    - auto_questions
    - title: "Ready to Begin"
      text: "Complete all questions for practice, then begin the real survey."
      highlight: "#submit-btn"
```

Set `enabled: false` to skip the tutorial.

## Environment Variables

| Variable | Default | Failure mode it prevents |
|----------|---------|--------------------------|
| `APP_ENV` | **none - required** | Booting with the security mode guessed. `production` or `dev`; anything else, including unset, refuses to start |
| `SECRET_KEY` | dev key (dev only) | Guessable session cookies. **Required when `APP_ENV=production`** |
| `ADMIN_PASSWORD` | `admin123` (dev only) | An open admin dashboard, which lists every participant email. **Required, non-default, when `APP_ENV=production`** |
| `DEV_MODE` | `false` | Nothing in production: `APP_ENV=production` + `DEV_MODE=true` refuses to boot (it auto-fills forms, shortens the study and bypasses referral codes) |
| `DATA_DIR` | (none) | Where the database and `audit.log` live. It no longer decides the mode - `APP_ENV` does |
| `REFERRAL_CODES` | (none) | Comma-separated access codes; empty = no gate |
| `SURVEY_CONFIG` | `survey_config.yaml` | The study definition. A config the app cannot boot on is refused at start, naming the key |
| `IMAGE_PAIRS_FILE` | the config's `data.file` | The trial rows, one per line, tab-separated |
| `TUTORIAL_PAIRS_FILE` | the config's tutorial data | The walkthrough's example trials, when the study has a tutorial |
| `SURVEY_DISABLE_SESSION_GATE` | `false` | Turns off the stale-session check. For the test suite only (hand-built sessions carry no version stamp); **`APP_ENV=production` refuses to boot with it set** |
| `RATELIMIT_STORAGE_URI` | `memory://` | Rate-limit counters. **Must be a `redis://` URL when `APP_ENV=production`**: with the in-process store every gunicorn worker counts its own traffic, so the limits in the code are a multiple of reality |
| `TILE_LAYOUT` | `MAB` | Tile order: `MAB` (Mask, A, B) or `AMB` |
| `PORT` | `5000` | Server port |

## Deployment

Build the frontend first: Vite emits `src/survey/static_dist/`, which the app serves at
`/dist/`. The build reads nothing from the environment, and a checkout with no build falls back
to `src/survey/static/`, so `npm` is only needed to change the frontend.

```bash
npm ci
npm run build
```

Then set `DATA_DIR` to a persistent directory and provide a strong `SECRET_KEY`:

```bash
export APP_ENV=production
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export ADMIN_PASSWORD="your-secure-password"
export DATA_DIR="/path/to/persistent/data"
gunicorn src.survey.app:app --bind 0.0.0.0:8000 --workers 4 --threads 2
```

Ask gunicorn for workers: its default is **one synchronous worker**, which serves every participant
one request at a time, and the production gate below exists precisely because several workers each
keep their own rate-limit counters.

`static_dist/` is read at boot, so a deploy replaces the code and the build together, then
restarts. The security mode comes from `APP_ENV` alone; `DATA_DIR` only says where the database and `audit.log` live. Production requires `SECRET_KEY` and a non-default `ADMIN_PASSWORD`, and enforces HTTPS cookies.

Rate limits are enforced per participant session, and the numbers are only real caps when the
counters are shared: point `RATELIMIT_STORAGE_URI` at redis so all workers count against one tally
and a restart does not reset it. The production boot refuses to start otherwise. The submit cap
follows the study (`pairs_per_user` + 20 per hour), so a participant can always finish the study
they started; login and delete-by-email stay fixed caps per address.

The app trusts exactly **one** `X-Forwarded-For` hop, because production terminates TLS at one
proxy in front of it. Put more than one proxy (or none) in front of the app and both the per-address
login cap and the `ip` field in `audit.log` are wrong: they name the nearest proxy, not the client.

`audit.log` entries are stamped in **UTC** from 2026-11-05, so an entry lines up with the database row
it explains (`CURRENT_TIMESTAMP` is UTC). Entries written before that date carry server-local time:
subtract the server's UTC offset when correlating an old deletion with a row.

## Admin Dashboard

Visit `/admin/login`. The dashboard provides:
- Per-question method preferences (generated from config)
- Average confidence scores and time per pair
- Demographics and response tables
- CSV export
- Delete-by-email for data removal requests

## Database

SQLite with JSON columns for demographics and responses. Migration from older schemas runs automatically on startup.

## Testing

```bash
pip install ".[dev]" && npm ci
python -m pytest tests/ -q
npm run test:unit
npm run test:e2e
```

The survey's rules (question gating, answer assembly, payload shape, progress) live in
`frontend/src/study-state.ts` with no DOM, so they are unit-tested directly; the components call
into it and own the DOM work.

## License

MIT. See [LICENSE](LICENSE).
