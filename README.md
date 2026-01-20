# PDF Screenshot Tool

Automatically capture screenshots of Adobe Acrobat pages when navigating through documents.

## Features

- **Automatic page detection**: Captures screenshots when you navigate pages in Adobe Acrobat/Reader
- **Window-only capture**: Screenshots only the PDF window, not your entire screen
- **Organized saving**: Files are saved with document name and timestamp
- **System tray integration**: Runs quietly in the background
- **Customizable settings**: Choose save location, capture delay, and more

## Requirements for Building

- Python 3.8 or higher
- Windows 10 or higher
- Inno Setup 6.x (for creating the installer)

## Quick Start (Development)

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the application:
   ```
   python src/main.py
   ```

## Building the Executable

### Option 1: Use the build script

1. Double-click `build.bat`
2. The executable will be created in `dist/PDFScreenshotTool.exe`

### Option 2: Manual build

1. Create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   pip install pyinstaller
   ```

3. Build with PyInstaller:
   ```
   pyinstaller pdf_screenshot_tool.spec --clean
   ```

## Creating the Installer

1. Download and install [Inno Setup](https://jrsoftware.org/isdl.php)
2. Open `installer.iss` in Inno Setup Compiler
3. Click **Build > Compile** (or press Ctrl+F9)
4. The installer will be created in `installer_output/`

## Project Structure

```
pdf_screenshot_tool/
├── src/
│   └── main.py              # Main application code
├── assets/
│   └── icon.ico             # Application icon (add your own)
├── requirements.txt         # Python dependencies
├── pdf_screenshot_tool.spec # PyInstaller configuration
├── installer.iss            # Inno Setup installer script
├── build.bat               # Windows build script
└── README.md               # This file
```

## Configuration

The application stores its configuration in:
```
%APPDATA%\PDFScreenshotTool\config.json
```

Configuration options:
- `save_folder`: Where screenshots are saved
- `enabled`: Whether automatic capture is active
- `capture_delay`: Seconds to wait after navigation before capturing

## How It Works

1. The application monitors keyboard input when Adobe Acrobat/Reader is the active window
2. When navigation keys are pressed (Page Up/Down, arrow keys, Home/End), it waits briefly for the page to render
3. It then captures the Acrobat window and saves the screenshot with the document name and timestamp

## Supported Navigation Keys

- Page Up / Page Down
- Up Arrow / Down Arrow
- Left Arrow / Right Arrow
- Home / End

## Adding a Custom Icon

1. Create a 256x256 pixel icon in `.ico` format
2. Save it as `assets/icon.ico`
3. Rebuild the application

## License

[Your license here]

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
