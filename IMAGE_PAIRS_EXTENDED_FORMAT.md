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
7. **`mask_url`** (URL) - Mask image (can show different regions as colors)

## Example

```
A person skiing on a mountain	Method-A	Method-B	https://example.com/a.jpg	https://example.com/b.jpg	https://example.com/id1.jpg,https://example.com/id2.jpg	https://example.com/mask.png
```

## Backward Compatibility

For backward compatibility, lines without identity and mask URLs will still work:

```
# Old format (still works)
A serene mountain landscape	Method-A	Method-B	https://example.com/a.jpg	https://example.com/b.jpg

# New format (with conditioning)
A serene mountain landscape	Method-A	Method-B	https://example.com/a.jpg	https://example.com/b.jpg	https://example.com/identity.jpg	https://example.com/mask.png
```

## Evaluation Questions

With this format, users will evaluate:
1. **Image Quality** - Overall quality and aesthetics
2. **Prompt Adherence** - How well it matches the text prompt
3. **Mask Adherence** - How well it follows the spatial mask constraints
4. **Identity Adherence** - How well it preserves the identity features

Each evaluation includes a choice (A/B/Equal) and confidence level (1-5).

