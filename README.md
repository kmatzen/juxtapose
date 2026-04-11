# Survey Web Application

A config-driven Flask survey for A/B evaluation studies. Define your survey structure in `survey_config.yaml` — demographics, stimuli, questions, and layout — and the app handles the rest.

## Quick Start

```bash
pip install -r requirements.txt
DEV_MODE=true python -m src.survey.app
```

Open `http://localhost:5000`. Dev mode auto-fills forms, limits to 3 trials, bypasses referral codes, and shows a red badge.

## Configuration

Everything is defined in `survey_config.yaml`. See the included file for a complete working example.

### Survey Settings

```yaml
survey:
  title: "Your Study Title"
  description: "Introductory text shown on the demographics page."
  contact_email: "you@example.com"
  pairs_per_user: 30          # trials per participant
  dev_pairs: 3                # trials in dev mode
  survey_heading: "Image Comparison"
  survey_instruction: "Please evaluate the following two images."
  next_button_text: "Next Image Pair"
  submit_button_text: "Submit Survey"
  # Consent (leave empty to hide)
  consent_text: "I consent to the collection of my responses for research."
  privacy_policy_url: ""      # link shown above consent checkbox
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

Supported types: `email`, `text`, `number`, `select`, `checkbox`, `radio`, `textarea`

### Data File

Tab-separated, one row per trial. Column order must match `data.columns`:

```yaml
data:
  file: "image_pairs.txt"
  columns: [prompt, method_a, method_b, image_a_url, image_b_url, mask_url, identity_urls]
```

```
a mountain landscape	Method-A	Method-B	https://...a.png	https://...b.png	https://...mask.png	https://...id.png
```

Lines starting with `#` are comments. A sample file is auto-created if missing.

### Inputs

Shared context shown for each trial. Each input maps a data column to a widget.

| Type | Description |
|------|-------------|
| `text` | Plain text in a prompt box |
| `image` | Single image (click to enlarge with `lightbox` interaction) |
| `image_gallery` | Row of images from comma-separated URLs or stacked image |
| `video` | HTML5 video player (supports `loop`, `controls` interactions) |
| `audio` | HTML5 audio player (supports `loop` interaction) |

```yaml
inputs:
  - name: prompt
    type: text
    label: "Text Prompt"
    column: prompt
  - name: mask
    type: image
    label: "Spatial Mask"
    column: mask_url
    optional: true          # hidden when column value is empty for this trial
    interactions: [lightbox]
```

### Outputs

Per-method results shown as A/B comparison. Position is randomized per trial.

| Type | Description |
|------|-------------|
| `image` | Side-by-side images |
| `video` | Side-by-side video players |
| `audio` | Side-by-side audio players |
| `text` | Side-by-side text blocks |

```yaml
outputs:
  - name: image
    type: image
    label: "Image"
    column_a: image_a_url
    column_b: image_b_url
    interactions: [lightbox]
```

### Questions

Evaluation criteria shown per trial. Rendered in order. Each question becomes a form section with progressive scroll navigation.

| Type | Description | Form fields |
|------|-------------|-------------|
| `ab_preference` | A/B/Equal radio choice with optional 1-5 confidence scale | `{name}_choice`, `{name}_confidence` |
| `likert` | Numeric scale (configurable via `scale`, default 5) | `{name}_value` |
| `free_text` | Open text response | `{name}_text` |
| `multiple_choice` | Single selection from `options` list | `{name}_value` |

```yaml
questions:
  - name: image_quality
    type: ab_preference
    label: "Which image looks better?"
    section_label: "Image Quality"   # heading above the question
    confidence: true                 # show 1-5 confidence scale
    required: true
  - name: mask_adherence
    type: ab_preference
    label: "Which image follows the mask better?"
    depends_on: mask                 # hidden when mask input has no data
  - name: overall_rating
    type: likert
    label: "Rate the overall quality"
    scale: 7                         # 1-7 scale
  - name: comments
    type: free_text
    label: "Any additional comments?"
```

### Methods

Maps column names to method A/B for randomization and preference tracking:

```yaml
methods:
  a: method_a
  b: method_b
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEV_MODE` | `false` | Auto-fill forms, fewer trials, bypass referral |
| `ADMIN_PASSWORD` | `admin123` | Admin dashboard password |
| `SECRET_KEY` | dev key | Flask session secret (**required in production**) |
| `REFERRAL_CODES` | (none) | Comma-separated access codes; empty = no gate |
| `TILE_LAYOUT` | `MAB` | Tile order: `MAB` (Mask, A, B) or `AMB` |
| `PORT` | `5000` | Server port |
| `DATA_DIR` | (none) | Persistent data directory; enables production mode |
| `IMAGE_PAIRS_FILE` | from config | Override data file path |
| `TUTORIAL_PAIRS_FILE` | `tutorial_image_pair.txt` | Tutorial trial data |

## Tutorial Mode

After demographics, participants see an interactive tutorial that walks through the interface before starting the real survey. The tutorial uses a separate data file (`tutorial_image_pair.txt`).

## Admin

Visit `/admin/login`. The dashboard shows:
- Per-question method preferences (dynamically generated from config)
- Average confidence scores and time per pair
- Demographics and response tables
- CSV export
- Delete-by-email for data removal requests

## Deployment

A `Dockerfile` and `Procfile` are included for container-based hosting. Set environment variables for production:

```bash
SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
ADMIN_PASSWORD="your-secure-password"
DATA_DIR="/data"              # persistent volume mount for database + logs
```

When `DATA_DIR` is set (or `/data` exists), the app enables production mode: requires `SECRET_KEY`, enforces HTTPS cookies, and stores data in that directory.

```bash
docker build -t survey .
docker run -p 8000:8000 \
  -v survey_data:/data \
  -e SECRET_KEY="..." \
  -e ADMIN_PASSWORD="..." \
  survey
```

## Database

SQLite with JSON columns for demographics and responses. Migration from older schemas runs automatically on startup.

- Development: `survey.db` (current directory)
- Production: `$DATA_DIR/survey.db`

## Testing

```bash
pip install -r requirements.txt
python -m pytest tests/ -q
```

62 tests, 78% coverage.
