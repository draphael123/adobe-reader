# PDF Screenshot Tool

**Version 2.1.0** - Automatically capture screenshots of Adobe Acrobat pages when navigating through documents. Perfect for compliance, documentation, and audit trails.

[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-blue)](https://www.microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

## ✨ Features

### Core Functionality
- **🔄 Automatic page detection**: Captures screenshots automatically when you navigate pages in Adobe Acrobat/Reader or Pro
- **🪟 Window-only capture**: Screenshots only the PDF window, not your entire screen
- **📁 Organized saving**: Files are automatically saved with document name and timestamp
- **🔕 System tray integration**: Runs quietly in the background with minimal resource usage
- **⚙️ Highly customizable**: Extensive settings for capture behavior, image format, and more

### Advanced Features
- **🧠 AI-powered duplicate detection**: Uses perceptual hashing to skip identical pages automatically
- **⌨️ Keyboard shortcuts**: Quick access to manual capture, pause/resume, and settings
- **📊 Statistics dashboard**: Track your captures, document history, and usage stats
- **🔄 Auto-update system**: Automatically checks for and downloads new versions
- **🎨 Improved installation**: Scrollable welcome screen with funnier, more engaging setup experience
- **🔔 Notifications**: Optional sound and system notifications when captures occur
- **💾 Session management**: Organize captures by session with batch export to ZIP/PDF

## 🚀 Quick Start

### For Users

1. **Download** the latest release from [pdfscreenshottool.com](https://pdfscreenshottool.com)
2. **Run** the installer (`PDFScreenshotTool_Setup.exe`)
3. **Complete** the welcome screen setup (everything is scrollable now!)
4. **Open** any PDF in Adobe Acrobat Reader or Pro
5. **Navigate** pages - screenshots capture automatically!

### For Developers

1. **Clone** this repository:
   ```bash
   git clone https://github.com/draphael123/adobe-reader.git
   cd adobe-reader
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run** the application:
   ```bash
   python src/main.py
   ```

## 🛠️ Building the Executable

### Option 1: Use the build script (Recommended)

1. Double-click `build.bat`
2. The executable will be created in `dist/PDFScreenshotTool.exe`

### Option 2: Manual build

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller
   ```

3. Build with PyInstaller:
   ```bash
   pyinstaller pdf_screenshot_tool.spec --clean
   ```

## 📦 Creating the Installer

1. Download and install [Inno Setup](https://jrsoftware.org/isdl.php)
2. Open `installer.iss` in Inno Setup Compiler
3. Click **Build > Compile** (or press Ctrl+F9)
4. The installer will be created in `installer_output/`

## 📁 Project Structure

```
adobe-reader/
├── src/
│   └── main.py              # Main application code
├── assets/
│   ├── icon.ico             # Application icon
│   ├── wizard_image.bmp     # Installer images
│   └── wizard_small_image.bmp
├── public/                  # Website files (for Vercel deployment)
│   ├── index.html
│   ├── landing-page.html
│   └── PDFScreenshotTool.exe
├── requirements.txt         # Python dependencies
├── pdf_screenshot_tool.spec # PyInstaller configuration
├── installer.iss            # Inno Setup installer script
├── build.bat               # Windows build script
├── build-for-deploy.ps1    # Deployment preparation script
├── vercel.json             # Vercel deployment configuration
└── README.md               # This file
```

## ⚙️ Configuration

The application stores its configuration in:
```
%APPDATA%\PDFScreenshotTool\config.json
```

### Key Configuration Options

- `save_folder`: Where screenshots are saved (default: Documents/PDF Screenshots)
- `enabled`: Whether automatic capture is active
- `capture_delay`: Seconds to wait after navigation before capturing (default: 0.3s)
- `capture_on_scroll`: Enable capture on mouse scroll (recommended)
- `duplicate_detection_enabled`: Enable AI-powered duplicate detection
- `duplicate_similarity_threshold`: Sensitivity for duplicate detection (0-64)
- `image_format`: Output format (png, jpeg, or webp)
- `start_with_windows`: Launch automatically on Windows startup

## 🎮 Keyboard Shortcuts

- **Ctrl+Shift+S**: Manual capture (force a screenshot)
- **Ctrl+Shift+P**: Pause/Resume automatic capture
- **Ctrl+Shift+O**: Open screenshots folder
- **Ctrl+Shift+,**: Open settings window

## 🔍 How It Works

1. The application monitors keyboard and mouse input when Adobe Acrobat/Reader is the active window
2. When navigation occurs (Page Up/Down, arrow keys, scroll, Home/End), it detects the page change
3. It waits briefly for the page to render (configurable delay)
4. Captures the Acrobat window using screen capture API
5. Applies duplicate detection (if enabled) using perceptual hashing
6. Saves the screenshot with organized naming: `DocumentName_Page_001.png`
7. Updates statistics and optionally plays sound/shows notification

## 📋 Supported Navigation Methods

- **Keyboard**: Page Up/Down, Arrow keys, Home/End
- **Mouse**: Scroll wheel (when enabled)
- **Manual**: Keyboard shortcut (Ctrl+Shift+S)

## 🧠 Duplicate Detection

The tool uses perceptual hashing (pHash) to detect similar pages:
- Compares image hashes to skip identical or near-identical pages
- Configurable similarity threshold (0 = exact match, higher = more lenient)
- Saves disk space and processing time
- Works even with slight variations (cursor position, minor rendering differences)

## 🆕 What's New in v2.1.0

- ✅ **Fixed**: Installation window scrolling (you can now see everything!)
- ✅ **Improved**: Welcome screen with funnier, more engaging text
- ✅ **New**: Perceptual hashing for smart duplicate detection
- ✅ **New**: Configurable similarity threshold
- ✅ **New**: Capture count in tray tooltip
- ✅ **New**: "View Last Capture" menu option
- ✅ **Improved**: First-run tutorial experience

See [CHANGELOG.md](CHANGELOG.md) for full version history.

## 🐛 Troubleshooting

### Windows SmartScreen Warning
Windows may warn about downloads from new developers. This is normal:
1. Click "More info"
2. Click "Run anyway"
3. The app is safe and open source

### Screenshots Not Capturing
- Ensure Adobe Acrobat/Reader is the active window
- Check that automatic capture is enabled (not paused)
- Verify the save folder exists and is writable
- Check the system tray icon color (blue = ready, green = capturing)

### High CPU Usage
- Disable duplicate detection if not needed
- Increase capture delay if capturing too frequently
- Check for multiple instances running

## 📝 Requirements

- **OS**: Windows 10 or Windows 11 (64-bit)
- **Python** (for development): 3.8 or higher
- **Adobe Acrobat**: Reader DC or Acrobat Pro (any recent version)
- **Admin rights**: Not required (runs without elevation)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

[Your license here]

## 🔗 Links

- **Website**: [pdfscreenshottool.com](https://pdfscreenshottool.com)
- **GitHub**: [github.com/draphael123/adobe-reader](https://github.com/draphael123/adobe-reader)
- **Issues**: [Report a bug or request a feature](https://github.com/draphael123/adobe-reader/issues)

## 👤 Author

**Daniel Raphael**

- Website: [pdfscreenshottool.com](https://pdfscreenshottool.com)
- GitHub: [@draphael123](https://github.com/draphael123)

---

Made with ❤️ for people who hate manual screenshots
