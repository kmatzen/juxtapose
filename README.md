# Survey Web Application

A config-driven Flask survey for A/B evaluation studies. Define your survey structure in `survey_config.yaml` — demographics, stimuli, questions, and layout — and the app handles the rest.

## Quick Start

```bash
pip install -r requirements.txt
DEV_MODE=true python -m src.survey.app
```

Dev mode auto-fills forms, limits to 3 trials, and bypasses referral codes.

## Configuration

Everything is defined in `survey_config.yaml`:

```yaml
survey:
  title: "Your Study Title"
  contact_email: "you@example.com"
  pairs_per_user: 30
  dev_pairs: 3

demographics:
  - name: email
    type: email
    label: "Email Address"
    required: true
  - name: occupation
    type: select
    label: "Occupation"
    options:
      - { value: "researcher", label: "Researcher" }
      # ...

data:
  file: "image_pairs.txt"
  columns: [prompt, method_a, method_b, image_a_url, image_b_url, mask_url, identity_urls]

methods:
  a: method_a
  b: method_b

inputs:
  - name: prompt
    type: text
    label: "Text Prompt"
    column: prompt
  - name: mask
    type: image
    label: "Spatial Mask"
    column: mask_url
    optional: true

outputs:
  - name: image
    type: image
    column_a: image_a_url
    column_b: image_b_url

questions:
  - name: image_quality
    type: ab_preference
    label: "Which image looks better?"
    confidence: true
    required: true
  - name: mask_adherence
    type: ab_preference
    label: "Which image follows the mask better?"
    confidence: true
    depends_on: mask
```

### Data File

Tab-separated, one row per trial. Column order must match `data.columns`:

```
a mountain landscape	Method-A	Method-B	https://...a.png	https://...b.png	https://...mask.png	https://...id.png
```

Lines starting with `#` are comments.

### Supported Types

**Demographics:** email, text, number, select, checkbox, radio, textarea

**Inputs:** text, image, image_gallery, video, audio

**Outputs:** image, video, audio, text

**Questions:** ab_preference (with optional confidence), likert, free_text, multiple_choice

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEV_MODE` | `false` | Auto-fill forms, 3 trials, bypass referral |
| `ADMIN_PASSWORD` | `admin123` | Admin dashboard password |
| `SECRET_KEY` | dev key | Flask session secret (required in production) |
| `REFERRAL_CODES` | `ADOBE2025` | Comma-separated access codes |
| `TILE_LAYOUT` | `MAB` | Tile order: `MAB` or `AMB` |
| `PORT` | `5000` | Server port |

## Admin

Visit `/admin/login`. The dashboard shows per-question method preferences, confidence stats, and timing. Export to CSV for analysis.

## Deployment (Fly.io)

```bash
fly launch --no-deploy --name your-survey
fly volumes create survey_data --size 3 --region sjc
fly secrets set ADMIN_PASSWORD="yourpass" SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
fly deploy
```

## Database

SQLite with JSON columns. Demographics and responses stored as JSON for flexibility. Migration from older schemas runs automatically on startup.

File: `survey.db` (local) or `/data/survey.db` (Fly.io).
