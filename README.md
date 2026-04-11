# Juxtapose

A config-driven web application for running A/B evaluation studies. Define your entire survey -- demographics, stimuli, evaluation questions, and tutorial -- in a single YAML file. No code changes needed.

Built for research teams who need to collect human judgments on generated content (images, video, audio, text) with proper randomization, progress tracking, and data export.

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
DEV_MODE=true python -m src.survey.app
```

Open http://localhost:5000. Dev mode auto-fills forms, limits to 3 trials, and bypasses referral codes.

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
| `text` | Plain text in a prompt box |
| `image` | Single image (supports lightbox) |
| `image_gallery` | Row of images from comma-separated URLs or stacked image |
| `video` | HTML5 video player (supports loop, controls) |
| `audio` | HTML5 audio player (supports loop) |

### Outputs

Per-method results shown as an A/B comparison. Position is randomized per trial.

| Type | Description |
|------|-------------|
| `image` | Side-by-side images |
| `video` | Side-by-side video players |
| `audio` | Side-by-side audio players |
| `text` | Side-by-side text blocks |

### Questions

Evaluation criteria per trial. Rendered in order with progressive scroll navigation.

| Type | Description | Form fields |
|------|-------------|-------------|
| `ab_preference` | A/B/Equal choice with optional confidence scale | `{name}_choice`, `{name}_confidence` |
| `likert` | Numeric scale (configurable range) | `{name}_value` |
| `free_text` | Open text response | `{name}_text` |
| `multiple_choice` | Single selection from options list | `{name}_value` |

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

| Variable | Default | Description |
|----------|---------|-------------|
| `DEV_MODE` | `false` | Auto-fill forms, fewer trials, bypass referral |
| `ADMIN_PASSWORD` | `admin123` | Admin dashboard password |
| `SECRET_KEY` | dev key | Flask session secret (**required in production**) |
| `REFERRAL_CODES` | (none) | Comma-separated access codes; empty = no gate |
| `DATA_DIR` | (none) | Persistent data directory; enables production mode |
| `TILE_LAYOUT` | `MAB` | Tile order: `MAB` (Mask, A, B) or `AMB` |
| `PORT` | `5000` | Server port |

## Deployment

For production, set `DATA_DIR` to a persistent directory and provide a strong `SECRET_KEY`:

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export ADMIN_PASSWORD="your-secure-password"
export DATA_DIR="/path/to/persistent/data"
gunicorn src.survey.app:app --bind 0.0.0.0:8000
```

When `DATA_DIR` is set, the app enables production mode: requires `SECRET_KEY`, enforces HTTPS cookies, and stores the database and audit log in that directory.

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
pip install ".[dev]"
python -m pytest tests/ -q
```

## License

MIT. See [LICENSE](LICENSE).
