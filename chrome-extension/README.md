# PDF Screenshot Tool - Chrome Extension

Chrome extension version of PDF Screenshot Tool with all features from the desktop application.

## Features

- ✅ Automatic PDF page capture
- ✅ Duplicate detection with perceptual hashing
- ✅ Page number detection
- ✅ Watermarking support
- ✅ Image cropping
- ✅ Statistics tracking
- ✅ Export to PowerPoint (planned)
- ✅ Export to PDF with bookmarks (planned)
- ✅ OCR text extraction (planned)
- ✅ Preview gallery
- ✅ Configurable settings

## Installation

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `chrome-extension` folder
5. The extension is now installed!

## Usage

1. Navigate to any PDF in Chrome
2. The extension will automatically detect the PDF
3. As you navigate pages, screenshots are captured automatically
4. Click the extension icon to see status and controls

## Development

### File Structure

```
chrome-extension/
├── manifest.json          # Extension manifest
├── background.js          # Service worker
├── content.js             # Content script for PDF detection
├── popup.html/js/css      # Extension popup UI
├── options.html           # Settings page
├── modules/               # JavaScript modules
│   ├── config.js
│   ├── hash-storage.js
│   ├── statistics.js
│   ├── image-processor.js
│   └── export-manager.js
└── icons/                 # Extension icons
```

### Building

No build step required - just load the unpacked extension in Chrome.

### Testing

1. Load extension in developer mode
2. Open a PDF in Chrome
3. Check console for logs
4. Test capture functionality
5. Verify settings persistence

## Notes

- Some features (PowerPoint export, OCR) may require additional libraries or API integration
- PDF capture works with Chrome's built-in PDF viewer
- For embedded PDFs, may need additional handling

## License

Same as main project

