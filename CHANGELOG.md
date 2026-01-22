# Changelog

All notable changes to PDF Screenshot Tool will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-01-27

### Fixed
- **Installation window scrolling**: Fixed issue where users couldn't scroll down in the installation welcome screen. Everything is now fully scrollable, so you can see all instructions and the "Start" button.

### Improved
- **Welcome screen text**: Updated installation welcome screen with funnier, more engaging copy. Installation doesn't have to be boring!
- **First-run tutorial**: Improved clarity and user experience during initial setup.

### Added
- **Perceptual hashing for duplicate detection**: AI-powered smart duplicate detection using perceptual hashing (pHash) to automatically skip identical or near-identical pages.
- **Configurable similarity threshold**: Adjust the sensitivity of duplicate detection (0-64, where 0 = exact match).
- **Capture count in tray tooltip**: See your capture count directly in the system tray tooltip for instant feedback.
- **"View Last Capture" menu option**: Quickly open the most recently captured screenshot.

## [2.0.0] - 2026-01-20

### Added
- **Auto-update system**: Automatic checking and downloading of new versions from GitHub releases.
- **Statistics dashboard**: Comprehensive statistics tracking including total captures, session data, document history, and usage analytics.
- **Session management**: Organize captures by session with dedicated folders and session tracking.
- **Batch export to ZIP/PDF**: Export multiple captures at once in organized ZIP files or combined PDFs.
- **Enhanced settings window**: More comprehensive settings with better organization and dark mode support.
- **Recent captures window**: View and manage your recent captures with preview thumbnails.

### Improved
- **Window detection**: More reliable detection of Adobe Acrobat windows.
- **File organization**: Better folder structure and naming conventions.
- **Error handling**: More robust error handling and user feedback.

## [1.0.0] - 2025-12-15

### Added
- Initial release
- Automatic page detection when navigating in Adobe Acrobat/Reader
- Window-only screenshot capture
- Organized file saving with document name and timestamp
- System tray integration
- Basic settings (save folder, capture delay)
- Keyboard shortcuts for manual capture, pause/resume, and folder access

---

[2.1.0]: https://github.com/draphael123/adobe-reader/releases/tag/v2.1.0
[2.0.0]: https://github.com/draphael123/adobe-reader/releases/tag/v2.0.0
[1.0.0]: https://github.com/draphael123/adobe-reader/releases/tag/v1.0.0

