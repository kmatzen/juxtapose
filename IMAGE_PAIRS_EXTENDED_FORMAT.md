# Extended Image Pairs File Format (with Identity & Mask Conditioning)

This document describes the extended format for `image_pairs.txt` that includes identity images and mask images as conditioning inputs.

## File Format

Each line represents a single image comparison pair with conditioning inputs (tab-separated):

```
prompt <TAB> method_a <TAB> method_b <TAB> image_a_url <TAB> image_b_url <TAB> identity_urls <TAB> mask_url
```

### Field Descriptions:

1. **`prompt`** (Text) - The text prompt used to generate the images
2. **`method_a`** (Text) - Method name for image A
3. **`method_b`** (Text) - Method name for image B
4. **`image_a_url`** (URL) - Generated image A
5. **`image_b_url`** (URL) - Generated image B
6. **`identity_urls`** (URLs) - Identity conditioning images, comma-separated if multiple
   - Example: `https://example.com/identity1.jpg,https://example.com/identity2.jpg`
   - Supports multiple identity reference images
7. **`mask_url`** (URL) - Mask image showing spatial layout constraints
   - Different colors can represent different regions/objects
   - Displayed to users as a reference for spatial adherence

## Example

```
A person skiing on a mountain	Method-A	Method-B	https://example.com/a.jpg	https://example.com/b.jpg	https://example.com/id1.jpg,https://example.com/id2.jpg	https://example.com/mask.png
```

## Backward Compatibility

**✅ FULLY BACKWARD COMPATIBLE** - The system works seamlessly with both formats:

```
# Old format (5 fields) - still works, no conditioning UI shown
A serene mountain landscape	Method-A	Method-B	https://example.com/a.jpg	https://example.com/b.jpg

# New format (7 fields) - shows conditioning UI and additional questions
A person skiing on a mountain	Method-A	Method-B	https://example.com/a.jpg	https://example.com/b.jpg	https://example.com/identity.jpg	https://example.com/mask.png
```

You can mix both formats in the same `image_pairs.txt` file!

## User Experience

### When Identity/Mask ARE Present:
- Yellow highlighted box displays identity reference images (clickable lightbox)
- Yellow highlighted box displays mask image (clickable lightbox)
- Users see **4 evaluation sections**:
  1. Image Quality (A/B/Equal + Confidence 1-5)
  2. Prompt Adherence (A/B/Equal + Confidence 1-5)
  3. **Mask Adherence** (A/B/Equal + Confidence 1-5) ⭐ NEW
  4. **Identity Preservation** (A/B/Equal + Confidence 1-5) ⭐ NEW

### When Identity/Mask ARE NOT Present:
- Conditioning boxes are hidden
- Users only see **2 evaluation sections**:
  1. Image Quality
  2. Prompt Adherence

The UI adapts automatically based on the data provided!

## Database Storage

Each response stores:
- `identity_urls` (TEXT) - Comma-separated URLs or NULL
- `mask_url` (TEXT) - Single URL or NULL
- `better_mask_match` (TEXT) - "A", "B", "equal", or NULL
- `mask_confidence` (INTEGER) - 1-5 or NULL
- `better_identity_match` (TEXT) - "A", "B", "equal", or NULL
- `identity_confidence` (INTEGER) - 1-5 or NULL

## Admin Analytics

The admin interface automatically calculates and displays:
- **Preferred Method (Mask)** - Which method better follows the mask
- **Preferred Method (Identity)** - Which method better preserves identity
- Shows "N/A" or "-" for responses without conditioning data
- CSV export includes all fields for comprehensive analysis

