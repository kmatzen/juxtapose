# Project Structure

This project follows the modern Python `src` layout for proper package organization.

## Directory Layout

```
survey/
├── src/
│   └── survey/              # Main package
│       ├── __init__.py      # Package initialization
│       ├── app.py           # Flask application
│       ├── templates/       # Jinja2 templates
│       │   ├── index.html
│       │   ├── admin.html
│       │   ├── admin_login.html
│       │   └── thank_you.html
│       └── static/          # Static assets
│           ├── style.css
│           └── script.js
│
├── pyproject.toml           # Project metadata & dependencies
├── requirements.txt         # Pip-compatible requirements (generated)
├── run.py                   # Entry point for local development
├── uv.lock                  # Locked dependencies (auto-generated)
│
├── render.yaml              # Render.com deployment config
├── fly.toml                 # Fly.io deployment config
├── Dockerfile               # Docker container config
├── Procfile                 # Process file for deployments
├── runtime.txt              # Python version specification
│
├── start.sh                 # Convenience startup script
├── sample_questions.py      # Example question format
│
├── README.md                # Main documentation
├── QUICKSTART.md            # Quick start guide
├── DEPLOYMENT.md            # Deployment instructions
├── UV_GUIDE.md              # uv usage guide
└── survey.db                # SQLite database (created at runtime)
```

## Benefits of `src` Layout

1. **Clean imports**: Package is properly installed, avoiding import issues
2. **Testing**: Tests run against installed package, not local files
3. **Distribution**: Easy to build wheels and publish to PyPI if needed
4. **Best practice**: Recommended by Python Packaging Authority (PyPA)

## Running the Application

### Development
```bash
# Install in editable mode
uv sync

# Run directly
uv run python run.py

# Or with the convenience script
./start.sh
```

### Production (via deployment platforms)
The application is started via gunicorn:
```bash
gunicorn src.survey.app:app
```

## Editing the Application

- **Main application logic**: `src/survey/app.py`
- **Question pairs**: Edit `QUESTION_PAIRS` in `src/survey/app.py`
- **Templates**: `src/survey/templates/`
- **Styles**: `src/survey/static/style.css`
- **Frontend JS**: `src/survey/static/script.js`

## Building & Installing

```bash
# Build the package
uv build

# Install in editable mode (for development)
uv sync

# Install from source
pip install -e .
```

## Deployment

All deployment configurations have been updated to use the proper module path:
- Gunicorn command: `gunicorn src.survey.app:app`
- All configs point to the correct package structure
