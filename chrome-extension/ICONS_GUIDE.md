# Icon Creation Guide

The Chrome extension needs icon files in the `icons/` folder.

## Required Icons

- `icon16.png` - 16x16 pixels (toolbar icon)
- `icon48.png` - 48x48 pixels (extension management)
- `icon128.png` - 128x128 pixels (Chrome Web Store)

## Creating Icons

### Option 1: Convert from Existing Icon

If you have the desktop app icon (`assets/icon.ico`):

1. Use an online converter or image editor
2. Convert ICO to PNG
3. Resize to required dimensions
4. Save as `icon16.png`, `icon48.png`, `icon128.png`

### Option 2: Create New Icons

1. Design a camera/screenshot icon
2. Create at 128x128 first
3. Scale down to 48x48 and 16x16
4. Ensure icons are clear at small sizes

### Option 3: Use Online Tools

- https://www.favicon-generator.org/
- https://realfavicongenerator.net/
- Any image editor (GIMP, Photoshop, etc.)

## Quick Solution

For testing, you can create simple placeholder icons:

1. Create a 128x128 PNG with a camera icon
2. Use the same image for all sizes (Chrome will scale)
3. Place in `icons/` folder

## Icon Design Tips

- Use simple, recognizable shapes
- High contrast colors
- Test at 16x16 to ensure readability
- Camera icon fits the app's purpose
- Match the desktop app's icon style if possible

