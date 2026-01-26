# Chrome Extension Testing Guide

## Known Issues & Fixes

### Issue 1: Missing Icons
**Problem**: The manifest references icon files that don't exist.

**Fix**: 
1. Create icon files:
   - `icons/icon16.png` (16x16 pixels)
   - `icons/icon48.png` (48x48 pixels)  
   - `icons/icon128.png` (128x128 pixels)

2. Or temporarily comment out icon references in manifest.json

### Issue 2: Image Processing in Service Worker
**Problem**: ImageProcessor uses DOM APIs (document, Image, canvas) which aren't available in service workers.

**Status**: Fixed - Image processing is now skipped in background.js. Watermark/crop features would need offscreen canvas API.

### Issue 3: PDF Detection
**Problem**: Chrome's PDF viewer may not be easily detectable.

**Status**: Content script attempts multiple detection methods. May need refinement based on Chrome version.

## Testing Steps

1. **Load Extension**:
   - Go to `chrome://extensions/`
   - Enable Developer mode
   - Click "Load unpacked"
   - Select the `chrome-extension` folder

2. **Check for Errors**:
   - Open Chrome DevTools (F12)
   - Go to Extensions tab
   - Check for any errors in background script

3. **Test PDF Detection**:
   - Open a PDF in Chrome (e.g., `https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf`)
   - Check console for "PDF Screenshot Tool: PDF detected" message

4. **Test Capture**:
   - Navigate to next page in PDF
   - Check Downloads folder for captured image
   - Check extension popup for statistics

5. **Test Settings**:
   - Right-click extension icon → Options
   - Change settings and save
   - Verify settings persist

## Common Issues

### Extension won't load
- Check manifest.json syntax
- Ensure all referenced files exist
- Check for JavaScript errors in console

### PDF not detected
- Chrome's PDF viewer structure may vary
- Check content script console logs
- Try different PDF URLs

### Capture not working
- Check background script console
- Verify permissions in manifest
- Check if downloads permission is granted

### Icons missing
- Create placeholder icons or remove icon references
- Extension will still work without icons

## Debugging

1. **Background Script**: Check `chrome://extensions/` → Service Worker → Inspect
2. **Content Script**: Check page console (F12 on PDF page)
3. **Popup**: Right-click extension icon → Inspect popup

## Next Steps

1. Create actual icon files
2. Test with various PDF sources
3. Refine PDF detection logic
4. Add offscreen canvas for image processing
5. Test duplicate detection
6. Verify statistics tracking

