# GenAI Image Evaluation Survey Guide

Your survey is now set up to compare **AI-generated images** instead of text questions.

## What Changed

### Survey Flow

**Participants now:**
1. Fill out demographics (AI/graphics background)
2. See 30 image pairs with their generation prompts
3. For each pair, evaluate:
   - **Image Quality**: Which image looks better? (A/B/Equal) + Confidence (1-5)
   - **Prompt Adherence**: Which better matches the prompt? (A/B/Equal) + Confidence (1-5)

### Data Collected Per Image Pair

- **Prompt**: The text used to generate the images
- **Image A & B URLs**: Links to the images
- **Better Image**: A, B, or Equal
- **Image Confidence**: 1-5 (how confident about quality assessment)
- **Better Prompt Match**: A, B, or Equal  
- **Prompt Confidence**: 1-5 (how confident about prompt match)
- **Randomized**: Whether A/B order was swapped

## How to Add Your 30 Image Pairs

### Step 1: Host Your Images

You need publicly accessible URLs for your images. Options:

#### Option A: S3/CloudFront (Recommended for production)
```bash
# Upload to S3
aws s3 cp pair1_a.jpg s3://your-bucket/images/
aws s3 cp pair1_b.jpg s3://your-bucket/images/

# Make public or use CloudFront
```

#### Option B: Cloudinary (Free tier: 25GB)
1. Sign up at cloudinary.com
2. Upload images via dashboard or API
3. Copy the image URLs

#### Option C: GitHub (Simple for small datasets)
1. Create `images/` folder in your repo
2. Add images to `.gitignore` if private data
3. Use raw GitHub URLs: `https://raw.githubusercontent.com/username/repo/main/images/pair1_a.jpg`

#### Option D: ImgBB (Free, no account needed)
Upload images to imgbb.com and copy direct links

### Step 2: Update IMAGE_PAIRS in app.py

Edit `src/survey/app.py` around line 18:

```python
IMAGE_PAIRS = [
    {
        "id": 1,
        "prompt": "A serene mountain landscape at sunset",
        "image_a_url": "https://your-cdn.com/images/mountain_a.jpg",
        "image_b_url": "https://your-cdn.com/images/mountain_b.jpg"
    },
    {
        "id": 2,
        "prompt": "A futuristic city with flying cars",
        "image_a_url": "https://your-cdn.com/images/city_a.jpg",
        "image_b_url": "https://your-cdn.com/images/city_b.jpg"
    },
    # ... 28 more pairs
]
```

### Step 3: Test Locally

```bash
uv run python run.py
# Visit http://localhost:5000
```

### Step 4: Deploy

```bash
git add src/survey/app.py
git commit -m "Add 30 image pairs for study"
git push
```

Render will auto-deploy the update.

## Image Requirements

### Technical Specs
- **Format**: JPG, PNG, WebP
- **Size**: 600x400 to 1200x800 pixels recommended
- **Max file size**: < 2MB per image (for fast loading)
- **Aspect ratio**: Consistent across pairs (e.g., all 3:2 or all 16:9)

### Content Recommendations
- Same prompt should generate comparable images
- Ensure images are appropriate for your audience
- Consider variety in prompts (different subjects, styles, complexity)
- Test that images load quickly on mobile

## Data Export

### Admin Dashboard

Visit `/admin/login` (password set via `ADMIN_PASSWORD` env var)

**Two views:**
1. **Demographics View**: Shows each participant's background + completion status
2. **Responses View**: Shows individual image evaluations

**Export**: Click "Export to CSV" for full dataset

### CSV Columns

- `email`, `occupation`, `technical_background`, etc.
- `image_pair_id`: Which pair (1-30)
- `prompt`: The text prompt
- `image_a_url`, `image_b_url`: Image URLs
- `better_image`: A/B/Equal
- `image_confidence`: 1-5
- `better_prompt_match`: A/B/Equal
- `prompt_confidence`: 1-5
- `was_randomized`: True/False

## Analysis Tips

### Key Metrics

1. **Agreement Rate**: How often do participants agree on which is better?
2. **Confidence Distribution**: Are people confident in their assessments?
3. **Quality vs Adherence**: Do images that look better also match prompts better?
4. **Randomization Check**: Does A/B order affect results?
5. **Demographics Correlation**: Do AI experts rate differently than novices?

### Sample Analysis (Python)

```python
import pandas as pd

# Load data
df = pd.read_csv('survey_results.csv')

# Agreement rate
agreement = df.groupby('image_pair_id')['better_image'].agg(
    lambda x: (x.mode()[0] if len(x.mode()) > 0 else 'varied', 
               (x == x.mode()[0]).sum() / len(x))
)

# Average confidence by experience
conf_by_exp = df.groupby('has_used_image_gen')[
    ['image_confidence', 'prompt_confidence']
].mean()

# Quality vs Adherence correlation
df['same_choice'] = df['better_image'] == df['better_prompt_match']
print(f"Quality matches adherence: {df['same_choice'].mean():.1%}")
```

## Troubleshooting

### Images not loading
- Check URLs are publicly accessible
- Test in incognito browser
- Check CORS settings if using S3
- Verify image files aren't too large

### Database issues
- Delete `survey.db` to reset (loses all data!)
- On Render free tier, database resets on sleep (normal)

### Participants can't submit
- Check they completed both confidence ratings
- Ensure all radio buttons are selected
- Check browser console for errors

## Next Steps

1. ✅ Demographics are customized for AI/graphics study
2. ✅ Survey structure supports image comparison
3. 🔲 Add your 30 actual image pairs
4. 🔲 Test with a few participants
5. 🔲 Deploy and share survey link
6. 🔲 Monitor responses in admin dashboard
7. 🔲 Export and analyze results

## Example Workflow

```bash
# 1. Generate images with your AI system
generate_images.py --prompt "mountain sunset" --output pair1/

# 2. Upload to hosting
aws s3 cp pair1/ s3://my-survey-images/ --recursive

# 3. Update app.py
# Edit IMAGE_PAIRS with S3 URLs

# 4. Test locally
uv run python run.py

# 5. Deploy
git add src/survey/app.py
git commit -m "Add study image pairs"
git push

# 6. Share with participants
# Send them: https://your-app.onrender.com
```

## Questions?

- Check `README.md` for general setup
- Check `DEPLOYMENT.md` for hosting options
- Check `sample_questions.py` (now sample images) for format

Your survey is ready for GenAI image evaluation research! 🎨🤖

