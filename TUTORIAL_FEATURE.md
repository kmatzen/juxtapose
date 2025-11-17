# Tutorial Feature Documentation

## Overview
A comprehensive tutorial/instructions page is now shown to users after completing demographics but before starting the survey. This helps users understand the interface, color coding, and hover features.

## Flow

```
User Journey:
1. Referral Code (if required) → 
2. Demographics Form → 
3. **Tutorial Page (NEW)** → 
4. Survey Questions
```

## Tutorial Content

The tutorial covers:

### 1. **Survey Purpose**
- Explains what users will be evaluating
- Three evaluation criteria: quality, identity adherence, mask adherence
- Confidence rating system

### 2. **Interface Components**
- Text prompt explanation
- Identity reference images (gold-bordered boxes)
- Spatial mask (gold-bordered box with colored regions)
- Generated images A and B (blue-bordered boxes)

### 3. **Color Coding System**
- Visual swatches showing all 7 identity colors
- Explanation of how border colors match mask regions
- Color list: Red, Green, Blue, Yellow, Magenta, Cyan, Orange

### 4. **Interactive Hover Feature**
- ✨ Highlighted pro tip explaining the hover functionality
- Instructions to hover over identity images to see highlighted regions in generated images

### 5. **Question Mechanics**
- Two-part answers: choice + confidence
- Auto-scroll behavior
- Confidence scale (1-5)

### 6. **Navigation**
- Scroll arrows for questions
- Progress bar
- Right arrow for next image pair
- Auto-save and resume capability

### 7. **Additional Tips**
- Lightbox feature for image viewing
- Important note styled with yellow highlight

## Implementation

### Backend Routes

**`/tutorial`** (GET)
- Checks referral validation
- Verifies demographics completed
- Renders `tutorial.html`

**`/api/complete_tutorial`** (POST)
- Marks tutorial as completed in session
- Returns `{"ok": true}`

### Session Flow Updates

The index route (`/`) now checks:
1. Referral validated? → Redirect to `/referral`
2. Demographics completed? → Check tutorial
3. Tutorial completed? → Show survey
4. Tutorial not completed? → Redirect to `/tutorial`

### Frontend

**Template**: `src/survey/templates/tutorial.html`
- Standalone styled page
- Responsive design
- Purple theme matching survey branding
- Interactive "Start Survey" button
- AJAX call to mark completion

### Styling

- **Header**: Purple (`#6a1b9a`) with centered layout
- **Sections**: Light gray background with purple left border
- **Examples**: Color-coded boxes matching actual interface
- **Color swatches**: Visual representation of identity colors
- **Hover demo**: Blue highlight box
- **Important note**: Yellow warning box
- **Button**: Purple with hover effect

## Features

### Visual Examples
- Shows styled example boxes for identity, mask, and generated images
- Color demo with actual color swatches
- Matches the real interface appearance

### Responsive Design
- Mobile-friendly layout
- Readable font sizes
- Flexible color demo grid

### User Control
- Clear "Start Survey" button
- One-click to proceed after reading

## Session Management

- Tutorial completion stored in session: `session['tutorial_completed'] = True`
- Persists across page navigation
- Resets when session is cleared

## Development Notes

### Skipping Tutorial
To skip the tutorial during development, you can manually set the session variable or clear it in the reset functionality.

### Customization
To update tutorial content:
1. Edit `src/survey/templates/tutorial.html`
2. Modify sections, add/remove content
3. Update styling in `<style>` block

### Testing
- Test with new session (clear cookies)
- Verify flow: demographics → tutorial → survey
- Check that tutorial only shows once per session
- Verify "Start Survey" redirects correctly

## Benefits

1. **User Education**: Clear instructions before starting
2. **Reduced Errors**: Users understand interface before evaluating
3. **Hover Feature Awareness**: Highlights the interactive overlay feature
4. **Color Coding Clarity**: Explains the identity-mask relationship
5. **Better Data Quality**: Informed users make better evaluations
6. **Professional Appearance**: Shows attention to user experience

## Notes

- Tutorial appears after demographics to avoid overwhelming users initially
- Shown once per session (doesn't repeat on page refresh)
- Cannot be skipped - users must click "Start Survey"
- Content can be easily updated without changing backend logic

