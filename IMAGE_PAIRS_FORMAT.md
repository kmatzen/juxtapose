# Image Pairs Configuration Format

## File: `image_pairs.txt`

The survey loads image pairs from a simple tab-separated text file. This makes it easy to configure your survey without editing Python code.

## Format

Each line contains 5 fields separated by TAB characters:

```
prompt <TAB> method_a <TAB> method_b <TAB> image_a_url <TAB> image_b_url
```

### Fields:

1. **prompt** - The text prompt shown to users
2. **method_a** - Nickname for the method that generated image A (e.g., "GPT-4", "DALL-E", "Stable-Diffusion")
3. **method_b** - Nickname for the method that generated image B
4. **image_a_url** - URL or path to image A
5. **image_b_url** - URL or path to image B

### Rules:

- Use **TAB** characters (not spaces) to separate fields
- Lines starting with `#` are comments and will be ignored
- Empty lines are ignored
- Prompts can contain spaces, commas, etc. (that's why we use tabs)
- You need at least 30 pairs for production (3 for dev mode)

## Example

```
# This is a comment
A serene mountain landscape at sunset	GPT-4-Vision	DALL-E-3	https://example.com/img1a.jpg	https://example.com/img1b.jpg
A futuristic city with flying cars	GPT-4-Vision	DALL-E-3	https://example.com/img2a.jpg	https://example.com/img2b.jpg
A cat wearing sunglasses	GPT-4-Vision	DALL-E-3	/static/images/img3a.jpg	/static/images/img3b.jpg
```

## Image URLs

You can use:
- **Full URLs**: `https://example.com/image.jpg`
- **Relative paths**: `/static/images/image.jpg` (place images in `src/survey/static/images/`)
- **Cloud storage**: S3, Google Cloud Storage, etc.

## Tips

### Using Excel/Google Sheets:
1. Create columns: Prompt, Method A, Method B, Image A URL, Image B URL
2. Fill in your data
3. Export as TSV (Tab-Separated Values)
4. Rename to `image_pairs.txt`

### Using a Text Editor:
1. Make sure to use TAB characters (press the Tab key)
2. Don't use spaces to align columns - only TAB

### Checking Your File:
The app will print errors on startup if the file is malformed:
```bash
uv run python run.py
```

Look for messages like:
- `✓ Loaded 30 image pairs from image_pairs.txt` (success!)
- `Warning: Line 5 has 4 fields (expected 5), skipping...` (missing field)

## Environment Variable

You can specify a different file:
```bash
export IMAGE_PAIRS_FILE=my_custom_pairs.txt
uv run python run.py
```

## What Happens on Startup

1. App looks for `image_pairs.txt` in the project root
2. If not found, creates a sample file with 3 placeholder pairs
3. Parses the file and loads all valid pairs
4. If errors, prints warnings but continues with valid pairs
5. If no valid pairs, app will fail to start

## Updating Pairs

After editing `image_pairs.txt`:
1. Restart your local server
2. Or redeploy to your hosting platform (Render, Fly.io, etc.)

The new pairs will be loaded on the next startup.

