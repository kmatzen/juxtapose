# Color Coding Guide

This document provides a quick reference for updating the color coding used in the survey interface. The colors link identity images to their corresponding regions in the spatial mask.

## How It Works

1. **Identity Images**: Each sliced identity image gets a colored border (4px width)
2. **Spatial Mask**: The mask image contains colored regions
3. **Color Mapping**: Each identity border color corresponds to a specific region color in the spatial mask

## Current Placeholder Colors

Update these in `src/survey/static/style.css` under the "COLOR CODING FOR IDENTITY IMAGES" section (around line 557):

| Identity Index | CSS Selector | Placeholder Color | Hex Code | Description |
|----------------|--------------|-------------------|----------|-------------|
| 0 | `[data-identity-index="0"]` | Orange | `#FF6B35` | First mask region |
| 1 | `[data-identity-index="1"]` | Teal | `#4ECDC4` | Second mask region |
| 2 | `[data-identity-index="2"]` | Yellow | `#F7B731` | Third mask region |
| 3 | `[data-identity-index="3"]` | Mint Green | `#A8E6CF` | Fourth mask region |
| 4 | `[data-identity-index="4"]` | Pink | `#FF6B9D` | Fifth mask region |
| 5 | `[data-identity-index="5"]` | Light Purple | `#95A7F5` | Sixth mask region |
| 6 | `[data-identity-index="6"]` | Bright Yellow | `#FFD93D` | Seventh mask region |
| 7 | `[data-identity-index="7"]` | Green | `#6BCF7F` | Eighth mask region |

## How to Update Colors

### Step 1: Identify Your Mask Region Colors
Look at your spatial mask image and identify the unique colors used for each region.

### Step 2: Update the CSS
In `src/survey/static/style.css`, find this section:

```css
/* Placeholder colors - update these to match your spatial mask regions */
.identity-image[data-identity-index="0"] {
    border-color: #FF6B35;  /* Orange - matches first mask region */
}

.identity-image[data-identity-index="1"] {
    border-color: #4ECDC4;  /* Teal - matches second mask region */
}
/* ... and so on ... */
```

### Step 3: Replace the Hex Codes
Replace each `border-color` hex code with the corresponding color from your spatial mask.

### Step 4: Add More Indices (if needed)
If you have more than 8 identities, add additional rules:

```css
.identity-image[data-identity-index="8"] {
    border-color: #YOUR_COLOR;  /* Description */
}
```

## Example: Replacing Placeholder Colors

If your spatial mask uses these actual colors:
- Region 0: Red (`#E74C3C`)
- Region 1: Blue (`#3498DB`)
- Region 2: Green (`#2ECC71`)

Update the CSS like this:

```css
.identity-image[data-identity-index="0"] {
    border-color: #E74C3C;  /* Red - matches first mask region */
}

.identity-image[data-identity-index="1"] {
    border-color: #3498DB;  /* Blue - matches second mask region */
}

.identity-image[data-identity-index="2"] {
    border-color: #2ECC71;  /* Green - matches third mask region */
}
```

## Visual Result

After updating, users will see:
- Each identity image with a 4px colored border
- The border color matches the corresponding colored region in the spatial mask
- This helps users understand which identity corresponds to which mask region

## Interactive Hover Overlay Feature

When users hover over an identity image, the system automatically:
1. Processes the spatial mask to extract a binary mask for that identity's color region
2. Creates a semi-transparent overlay on Images A and B
3. Highlights the regions that correspond to that identity

### How It Works
- The mask image is processed pixel-by-pixel when loaded
- Each unique color in the mask is extracted into a separate binary mask
- On hover, the corresponding region is highlighted with a semi-transparent overlay using the identity's border color
- The overlay disappears when the mouse leaves the identity image

### Technical Details
- Color matching uses a tolerance of ±10 RGB values to account for compression artifacts
- Overlays are rendered using HTML5 Canvas for performance
- The feature gracefully fails if CORS restrictions prevent mask processing
- Color definitions are in `script.js` in the `IDENTITY_COLORS` array

### Adding More Colors
If you need to support more than 7 identities, update **both**:
1. The CSS rules (as described above)
2. The `IDENTITY_COLORS` array in `src/survey/static/script.js`:

```javascript
const IDENTITY_COLORS = [
    [255, 0, 0],      // 0: Red
    [0, 255, 0],      // 1: Green
    [0, 0, 255],      // 2: Blue
    [255, 255, 0],    // 3: Yellow
    [255, 0, 255],    // 4: Magenta
    [0, 255, 255],    // 5: Cyan
    [255, 128, 0],    // 6: Orange
    // Add your new color here: [R, G, B]
];
```

## Notes

- The spatial mask tile container uses the same gold/yellow theme as the identity reference boxes for visual consistency
- If you want to change the mask tile container styling, update the `.tile-box.mask-tile` rules around line 263 in the CSS
- Default border color for unmatched identity indices is gray (`#999`)
- Hover overlays require proper CORS headers on mask images; if unavailable, the feature silently disables

