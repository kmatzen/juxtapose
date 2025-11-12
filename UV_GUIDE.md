# Using uv with this Project

This project uses **uv** - an extremely fast Python package installer and resolver written in Rust by Astral (makers of ruff).

## Why uv?

- **10-100x faster** than pip
- Better dependency resolution
- Automatic virtual environment management
- Modern `pyproject.toml` support
- Compatible with pip/PyPI ecosystem

## Installation

### Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv

# Or with homebrew
brew install uv
```

## Quick Start

### 1. Install dependencies

```bash
uv sync
```

This creates a virtual environment (`.venv`) and installs all dependencies from `pyproject.toml`.

### 2. Run the app

```bash
uv run python app.py
```

Or use the convenience script:

```bash
./start.sh
```

## Common uv Commands

### Add a new dependency
```bash
uv add package-name
```

### Add a dev dependency
```bash
uv add --dev pytest
```

### Remove a dependency
```bash
uv remove package-name
```

### Update dependencies
```bash
uv sync --upgrade
```

### Run a command in the venv
```bash
uv run python script.py
uv run flask run
uv run gunicorn app:app
```

### Install project in editable mode
```bash
uv pip install -e .
```

## Project Structure

```
survey/
├── pyproject.toml    # Project config & dependencies (replaces requirements.txt)
├── uv.lock          # Locked dependency versions (auto-generated)
├── .venv/           # Virtual environment (auto-created)
└── app.py           # Your Flask app
```

## Deployment with uv

### Render.com

The `render.yaml` is already configured to use uv:

```yaml
buildCommand: |
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.cargo/bin:$PATH"
  uv sync
```

### Fly.io

Uses the included `Dockerfile` which has uv built-in.

```bash
fly deploy
```

### Railway

Railway will auto-detect `pyproject.toml`. If needed, add build command:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh && uv sync
```

## Migrating from requirements.txt

If you have a `requirements.txt`, convert it:

```bash
# uv can read requirements.txt and add to pyproject.toml
uv add $(cat requirements.txt)
```

Or manually edit `pyproject.toml`:

```toml
[project]
dependencies = [
    "flask>=3.0.0",
    "gunicorn>=21.2.0",
]
```

## Compatibility

uv is **fully compatible** with pip and PyPI:
- Uses the same package index (PyPI)
- Works with all pip packages
- Can run alongside pip (they don't conflict)

## Fallback to pip

If you prefer pip, you can still use `requirements.txt`:

```bash
# Generate requirements.txt from pyproject.toml
uv pip compile pyproject.toml -o requirements.txt

# Then use pip as normal
pip install -r requirements.txt
```

## Troubleshooting

### uv command not found

Add to PATH:
```bash
export PATH="$HOME/.cargo/bin:$PATH"
```

Add to your `~/.bashrc` or `~/.zshrc`:
```bash
echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.zshrc
```

### Virtual environment issues

Delete and recreate:
```bash
rm -rf .venv
uv sync
```

### Deployment errors

Most deployment platforms expect `requirements.txt`. Generate it:
```bash
uv pip compile pyproject.toml -o requirements.txt
```

Then commit both files to git.

## Learn More

- **uv docs**: https://docs.astral.sh/uv/
- **GitHub**: https://github.com/astral-sh/uv
- **Astral blog**: https://astral.sh/blog

## Speed Comparison

Installing Flask + dependencies:

- **pip**: ~10-15 seconds
- **uv**: ~1-2 seconds

Installing 100 packages:

- **pip**: ~2-3 minutes
- **uv**: ~10-15 seconds

The difference is **massive** on larger projects!

