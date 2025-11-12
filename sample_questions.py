"""
Sample image pairs for the survey.

Copy this structure to app.py and replace the IMAGE_PAIRS list with your actual images.
Each entry needs: id, prompt, image_a_url, and image_b_url
"""

SAMPLE_IMAGE_PAIRS = [
    {
        "id": 1,
        "prompt": "A serene mountain landscape at sunset",
        "image_a_url": "https://your-storage.com/images/pair1_a.jpg",
        "image_b_url": "https://your-storage.com/images/pair1_b.jpg"
    },
    {
        "id": 2,
        "prompt": "A futuristic city with flying cars",
        "image_a_url": "https://your-storage.com/images/pair2_a.jpg",
        "image_b_url": "https://your-storage.com/images/pair2_b.jpg"
    },
    {
        "id": 3,
        "prompt": "A cozy library with warm lighting",
        "image_a_url": "https://your-storage.com/images/pair3_a.jpg",
        "image_b_url": "https://your-storage.com/images/pair3_b.jpg"
    },
    {
        "id": 4,
        "prompt": "An underwater coral reef teeming with life",
        "image_a_url": "https://your-storage.com/images/pair4_a.jpg",
        "image_b_url": "https://your-storage.com/images/pair4_b.jpg"
    },
    {
        "id": 5,
        "prompt": "A steampunk-inspired mechanical dragon",
        "image_a_url": "https://your-storage.com/images/pair5_a.jpg",
        "image_b_url": "https://your-storage.com/images/pair5_b.jpg"
    },
    # Add 25 more image pairs below...
    # Template:
    # {
    #     "id": N,
    #     "prompt": "Your text prompt used to generate the images",
    #     "image_a_url": "URL or path to image A",
    #     "image_b_url": "URL or path to image B"
    # },
]

# Instructions:
# 1. Create 30 total image pairs (5 samples provided above)
# 2. Make sure each id is unique (1-30)
# 3. The prompt is the text used to generate the images
# 4. image_a_url and image_b_url point to the generated images
# 5. Images can be:
#    - Hosted on a CDN (S3, Cloudinary, etc.)
#    - GitHub raw URLs
#    - Any publicly accessible image URL
# 6. Recommended image size: 600x400 to 1200x800 pixels
# 7. Copy the completed list to src/survey/app.py, replacing the IMAGE_PAIRS variable

# Image Hosting Options:
# - AWS S3 + CloudFront
# - Cloudinary (free tier: 25GB storage)
# - ImgBB (free image hosting)
# - GitHub (for smaller datasets)
# - Your own server/Render static files

