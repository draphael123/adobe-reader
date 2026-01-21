"""
PDF Screenshot Tool
Automatically captures screenshots of Adobe Acrobat pages during navigation.
"""

import sys
import os
import threading
import time
import ctypes
import logging
import shutil
import zipfile
import winsound
import subprocess
import tempfile
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
import hashlib

import pystray
from PIL import Image, ImageDraw
from pynput import keyboard, mouse
import pygetwindow as gw
import mss
import mss.tools
import json

# Application version
APP_VERSION = "2.1.0"
GITHUB_REPO = "draphael123/adobe-reader"
UPDATE_CHECK_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
DOWNLOAD_PAGE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"

# Single instance check using Windows mutex
SINGLE_INSTANCE_MUTEX = None

def check_single_instance():
    """Ensure only one instance of the application runs at a time."""
    global SINGLE_INSTANCE_MUTEX
    
    mutex_name = "PDFScreenshotTool_SingleInstance_Mutex"
    
    try:
        # Try to create a named mutex
        SINGLE_INSTANCE_MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        last_error = ctypes.windll.kernel32.GetLastError()
        
        # ERROR_ALREADY_EXISTS = 183
        if last_error == 183:
            # Another instance is running - show message
            show_already_running_message()
            sys.exit(0)
            
    except Exception as e:
        # If mutex check fails, continue anyway
        pass


def show_already_running_message():
    """Show a message that the app is already running."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        
        # Create hidden root window
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        messagebox.showinfo(
            "PDF Screenshot Tool",
            "PDF Screenshot Tool is already running!\n\n"
            "Look for the camera icon in your system tray\n"
            "(bottom-right corner of your screen, near the clock).\n\n"
            "Right-click the icon to access settings or quit.",
            parent=root
        )
        
        root.destroy()
    except Exception:
        # Fallback to Windows message box if tkinter fails
        ctypes.windll.user32.MessageBoxW(
            0,
            "PDF Screenshot Tool is already running!\n\n"
            "Look for the camera icon in your system tray.",
            "PDF Screenshot Tool",
            0x40  # MB_ICONINFORMATION
        )


# Check for single instance before anything else
check_single_instance()

# Enable DPI awareness for correct screenshots on high-DPI displays
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # Fallback for older Windows
    except Exception:
        pass

# Configuration file path
CONFIG_DIR = Path(os.environ.get('APPDATA', Path.home())) / 'PDFScreenshotTool'
CONFIG_FILE = CONFIG_DIR / 'config.json'
LOG_FILE = CONFIG_DIR / 'app.log'
STATS_FILE = CONFIG_DIR / 'stats.json'
PORTABLE_FLAG = Path(__file__).parent.parent / '.portable'

# Check for portable mode
if PORTABLE_FLAG.exists():
    CONFIG_DIR = Path(__file__).parent.parent / 'data'
    CONFIG_FILE = CONFIG_DIR / 'config.json'
    LOG_FILE = CONFIG_DIR / 'app.log'
    STATS_FILE = CONFIG_DIR / 'stats.json'

# Setup logging
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    # Basic settings
    'save_folder': str(Path.home() / 'Documents' / 'PDF Screenshots'),
    'enabled': True,
    'start_with_windows': False,
    'dark_mode': True,
    'portable_mode': PORTABLE_FLAG.exists(),
    
    # Capture behavior
    'capture_delay': 0.3,  # seconds to wait after navigation
    'capture_cooldown': 0.5,  # minimum time between any captures
    'capture_on_scroll': True,
    'capture_on_click': False,  # capture on mouse click in Acrobat
    'min_scroll_distance': 50,  # minimum pixels scrolled before capture
    'max_captures_per_document': 0,  # 0 = unlimited
    'capture_document_only': False,  # crop to document area
    
    # Image settings
    'image_format': 'png',  # 'png', 'jpeg', or 'webp'
    'jpeg_quality': 90,
    'max_image_width': 0,  # 0 = no limit
    'max_image_height': 0,  # 0 = no limit
    'grayscale_mode': False,  # convert to grayscale
    'add_border': False,  # add border around capture
    'border_size': 10,  # border size in pixels
    'border_color': '#ffffff',  # border color
    
    # File organization
    'organize_by_document': True,  # create subfolders per document
    'organize_by_date': False,  # create date-based subfolders
    'date_folder_format': 'daily',  # 'daily', 'weekly', 'monthly'
    'max_files_per_folder': 0,  # 0 = unlimited
    'filename_template': '{document}_{date}_{time}',  # filename pattern
    
    # Hotkeys
    'hotkey_enabled': True,
    'manual_hotkey': 'ctrl+shift+s',
    'pause_hotkey': 'ctrl+shift+p',
    'open_folder_hotkey': 'ctrl+shift+o',
    'open_settings_hotkey': 'ctrl+shift+,',
    
    # Notifications
    'show_notifications': True,
    'notification_duration': 3,  # seconds
    'sound_enabled': True,
    'sound_volume': 100,  # 0-100
    'custom_sound_file': '',  # path to custom .wav file
    
    # Auto-cleanup
    'auto_cleanup_enabled': False,
    'auto_cleanup_days': 30,
    
    # Filters
    'filename_whitelist': '',  # comma-separated patterns to include
    'filename_blacklist': '',  # comma-separated patterns to exclude
    'min_window_width': 200,  # minimum window width to capture
    'min_window_height': 200,  # minimum window height to capture
    
    # Auto-update
    'auto_update_check': True,  # check for updates on startup
    'update_check_interval': 24,  # hours between update checks
    'last_update_check': None,  # timestamp of last check
    'skipped_version': None,  # version user chose to skip
}

# Default statistics
DEFAULT_STATS = {
    'total_captures': 0,
    'session_captures': 0,
    'total_size_bytes': 0,
    'documents_captured': [],
    'captures_by_date': {},
    'last_capture_time': None,
    'first_run_date': None,
}


class Statistics:
    """Manages application statistics."""
    
    def __init__(self):
        self.stats = DEFAULT_STATS.copy()
        self.session_start = datetime.now()
        self.load()
        
        # Initialize first run date
        if self.stats.get('first_run_date') is None:
            self.stats['first_run_date'] = datetime.now().isoformat()
            self.save()
    
    def load(self):
        """Load statistics from file."""
        try:
            if STATS_FILE.exists():
                with open(STATS_FILE, 'r') as f:
                    saved_stats = json.load(f)
                    self.stats.update(saved_stats)
        except Exception as e:
            logger.error(f"Error loading stats: {e}")
    
    def save(self):
        """Save statistics to file."""
        try:
            with open(STATS_FILE, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving stats: {e}")
    
    def record_capture(self, filepath, doc_name):
        """Record a capture event."""
        self.stats['total_captures'] += 1
        self.stats['session_captures'] += 1
        self.stats['last_capture_time'] = datetime.now().isoformat()
        
        # Track file size
        try:
            size = Path(filepath).stat().st_size
            self.stats['total_size_bytes'] += size
        except Exception:
            pass
        
        # Track by date
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in self.stats['captures_by_date']:
            self.stats['captures_by_date'][today] = 0
        self.stats['captures_by_date'][today] += 1
        
        # Track documents (limit to last 50)
        if doc_name not in self.stats['documents_captured']:
            self.stats['documents_captured'].append(doc_name)
            if len(self.stats['documents_captured']) > 50:
                self.stats['documents_captured'] = self.stats['documents_captured'][-50:]
        
        self.save()
    
    def get_summary(self):
        """Get a summary of statistics."""
        total_size_mb = self.stats['total_size_bytes'] / (1024 * 1024)
        
        # Calculate days since first run
        if self.stats.get('first_run_date'):
            first_run = datetime.fromisoformat(self.stats['first_run_date'])
            days_active = (datetime.now() - first_run).days + 1
        else:
            days_active = 1
        
        avg_per_day = self.stats['total_captures'] / days_active if days_active > 0 else 0
        
        return {
            'total_captures': self.stats['total_captures'],
            'session_captures': self.stats['session_captures'],
            'total_size_mb': round(total_size_mb, 2),
            'documents_count': len(self.stats['documents_captured']),
            'days_active': days_active,
            'avg_per_day': round(avg_per_day, 1),
        }


class Config:
    """Manages application configuration."""
    
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.is_first_run = not CONFIG_FILE.exists()
        self.load()
    
    def load(self):
        """Load configuration from file."""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
            logger.info("Configuration loaded")
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    
    def save(self):
        """Save configuration to file."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def get(self, key):
        return self.config.get(key, DEFAULT_CONFIG.get(key))
    
    def set(self, key, value):
        self.config[key] = value
        self.save()


class UpdateChecker:
    """Handles checking for and downloading updates."""
    
    def __init__(self, config):
        self.config = config
        self.latest_version = None
        self.download_url = None
        self.release_notes = None
        self.checking = False
    
    def parse_version(self, version_str):
        """Parse version string into tuple for comparison."""
        try:
            # Remove 'v' prefix if present
            v = version_str.strip().lstrip('v')
            parts = v.split('.')
            return tuple(int(p) for p in parts[:3])
        except:
            return (0, 0, 0)
    
    def is_newer_version(self, latest, current):
        """Check if latest version is newer than current."""
        return self.parse_version(latest) > self.parse_version(current)
    
    def should_check(self):
        """Determine if we should check for updates based on interval."""
        if not self.config.get('auto_update_check'):
            return False
        
        last_check = self.config.get('last_update_check')
        if not last_check:
            return True
        
        try:
            last_check_time = datetime.fromisoformat(last_check)
            hours_since = (datetime.now() - last_check_time).total_seconds() / 3600
            return hours_since >= self.config.get('update_check_interval')
        except:
            return True
    
    def check_for_updates(self, force=False, callback=None):
        """Check GitHub releases for updates. Runs in background thread."""
        if self.checking:
            return
        
        if not force and not self.should_check():
            logger.debug("Skipping update check (not due yet)")
            return
        
        def check_thread():
            self.checking = True
            try:
                logger.info("Checking for updates...")
                
                # Create request with headers
                req = urllib.request.Request(
                    UPDATE_CHECK_URL,
                    headers={
                        'User-Agent': f'PDFScreenshotTool/{APP_VERSION}',
                        'Accept': 'application/vnd.github.v3+json'
                    }
                )
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode('utf-8'))
                
                self.latest_version = data.get('tag_name', '').lstrip('v')
                self.release_notes = data.get('body', '')
                
                # Find the installer asset
                assets = data.get('assets', [])
                for asset in assets:
                    if 'Setup' in asset.get('name', '') and asset.get('name', '').endswith('.exe'):
                        self.download_url = asset.get('browser_download_url')
                        break
                
                # Fallback to release page if no direct download found
                if not self.download_url:
                    self.download_url = data.get('html_url', DOWNLOAD_PAGE_URL)
                
                # Update last check time
                self.config.set('last_update_check', datetime.now().isoformat())
                
                # Check if newer version available
                if self.latest_version and self.is_newer_version(self.latest_version, APP_VERSION):
                    # Check if user skipped this version
                    skipped = self.config.get('skipped_version')
                    if skipped != self.latest_version:
                        logger.info(f"New version available: {self.latest_version}")
                        if callback:
                            callback(self.latest_version, self.release_notes, self.download_url)
                    else:
                        logger.info(f"Version {self.latest_version} was skipped by user")
                else:
                    logger.info(f"No updates available (current: {APP_VERSION}, latest: {self.latest_version})")
                    if callback:
                        callback(None, None, None)  # Signal no update
                        
            except urllib.error.URLError as e:
                logger.warning(f"Could not check for updates (network error): {e}")
                if callback:
                    callback(None, None, None)
            except Exception as e:
                logger.error(f"Error checking for updates: {e}")
                if callback:
                    callback(None, None, None)
            finally:
                self.checking = False
        
        thread = threading.Thread(target=check_thread, daemon=True)
        thread.start()
    
    def download_and_install(self, callback=None):
        """Download the update and run the installer."""
        if not self.download_url:
            logger.error("No download URL available")
            return
        
        def download_thread():
            try:
                logger.info(f"Downloading update from: {self.download_url}")
                
                if callback:
                    callback('downloading', 0)
                
                # Download to temp directory
                temp_dir = Path(tempfile.gettempdir())
                installer_path = temp_dir / f"PDFScreenshotTool_Setup_{self.latest_version}.exe"
                
                req = urllib.request.Request(
                    self.download_url,
                    headers={'User-Agent': f'PDFScreenshotTool/{APP_VERSION}'}
                )
                
                with urllib.request.urlopen(req, timeout=60) as response:
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    chunk_size = 8192
                    
                    with open(installer_path, 'wb') as f:
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if callback and total_size > 0:
                                progress = int((downloaded / total_size) * 100)
                                callback('downloading', progress)
                
                logger.info(f"Download complete: {installer_path}")
                
                if callback:
                    callback('installing', 100)
                
                # Run the installer (this will close the current app)
                logger.info("Launching installer...")
                subprocess.Popen([str(installer_path)], shell=True)
                
                # Exit the current app to allow update
                if callback:
                    callback('done', 100)
                
            except Exception as e:
                logger.error(f"Error downloading update: {e}")
                if callback:
                    callback('error', str(e))
        
        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()
    
    def skip_version(self, version):
        """Mark a version as skipped."""
        self.config.set('skipped_version', version)
        logger.info(f"Skipped version: {version}")
    
    def open_download_page(self):
        """Open the download page in the default browser."""
        import webbrowser
        url = self.download_url or DOWNLOAD_PAGE_URL
        webbrowser.open(url)
        logger.info(f"Opened download page: {url}")


def get_executable_path():
    """Get the path to the current executable."""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return sys.executable
    else:
        # Running as script
        return sys.executable + ' "' + os.path.abspath(__file__) + '"'


def set_startup_registry(enable=True):
    """Add or remove the app from Windows startup."""
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "PDFScreenshotTool"
        
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        
        if enable:
            exe_path = get_executable_path()
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
            logger.info("Added to Windows startup")
        else:
            try:
                winreg.DeleteValue(key, app_name)
                logger.info("Removed from Windows startup")
            except FileNotFoundError:
                pass  # Already removed
        
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.error(f"Error setting startup registry: {e}")
        return False


def is_startup_enabled():
    """Check if app is set to start with Windows."""
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "PDFScreenshotTool"
        
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, app_name)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


def play_capture_sound(config=None):
    """Play a camera shutter sound."""
    try:
        custom_sound = config.get('custom_sound_file') if config else ''
        
        if custom_sound and Path(custom_sound).exists():
            # Play custom sound file
            winsound.PlaySound(custom_sound, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            # Use Windows system sound
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        pass


def parse_filename_template(template, doc_name, config=None):
    """Parse filename template and return formatted filename."""
    now = datetime.now()
    
    replacements = {
        '{document}': doc_name,
        '{date}': now.strftime('%Y%m%d'),
        '{time}': now.strftime('%H%M%S'),
        '{datetime}': now.strftime('%Y%m%d_%H%M%S'),
        '{year}': now.strftime('%Y'),
        '{month}': now.strftime('%m'),
        '{day}': now.strftime('%d'),
        '{hour}': now.strftime('%H'),
        '{minute}': now.strftime('%M'),
        '{second}': now.strftime('%S'),
        '{ms}': now.strftime('%f')[:3],
    }
    
    result = template
    for key, value in replacements.items():
        result = result.replace(key, value)
    
    # Clean filename of invalid characters
    result = "".join(c for c in result if c.isalnum() or c in (' ', '-', '_', '.')).strip()
    
    return result if result else f"{doc_name}_{now.strftime('%Y%m%d_%H%M%S')}"


def matches_filter(text, filter_patterns):
    """Check if text matches any of the comma-separated patterns."""
    if not filter_patterns:
        return False
    
    patterns = [p.strip().lower() for p in filter_patterns.split(',') if p.strip()]
    text_lower = text.lower()
    
    for pattern in patterns:
        if pattern in text_lower:
            return True
    return False


def cleanup_old_screenshots(folder, days):
    """Delete screenshots older than specified days."""
    if days <= 0:
        return 0
    
    deleted = 0
    cutoff = datetime.now() - timedelta(days=days)
    folder_path = Path(folder)
    
    if not folder_path.exists():
        return 0
    
    try:
        for file in folder_path.rglob('*'):
            if file.is_file() and file.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                try:
                    mtime = datetime.fromtimestamp(file.stat().st_mtime)
                    if mtime < cutoff:
                        file.unlink()
                        deleted += 1
                        logger.info(f"Cleaned up old screenshot: {file}")
                except Exception as e:
                    logger.error(f"Error deleting {file}: {e}")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    
    return deleted


class SessionManager:
    """Manages capture sessions."""
    
    def __init__(self, config):
        self.config = config
        self.current_session = None
        self.session_captures = []
        self.session_start = None
    
    def start_session(self, name=None):
        """Start a new capture session."""
        if name is None:
            name = datetime.now().strftime("Session_%Y%m%d_%H%M%S")
        
        self.current_session = name
        self.session_captures = []
        self.session_start = datetime.now()
        logger.info(f"Started session: {name}")
        return name
    
    def end_session(self):
        """End the current session."""
        if self.current_session:
            logger.info(f"Ended session: {self.current_session} ({len(self.session_captures)} captures)")
        
        session_info = {
            'name': self.current_session,
            'captures': self.session_captures.copy(),
            'start': self.session_start.isoformat() if self.session_start else None,
            'end': datetime.now().isoformat()
        }
        
        self.current_session = None
        self.session_captures = []
        self.session_start = None
        
        return session_info
    
    def add_capture(self, filepath):
        """Add a capture to the current session."""
        self.session_captures.append(filepath)
    
    def get_session_folder(self):
        """Get the folder for the current session."""
        if self.current_session:
            base_folder = Path(self.config.get('save_folder'))
            return base_folder / 'Sessions' / self.current_session
        return None


class AcrobatMonitor:
    """Monitors Adobe Acrobat for page navigation."""
    
    ACROBAT_TITLES = ['Adobe Acrobat', 'Adobe Reader', 'Acrobat Reader']
    NAVIGATION_KEYS = [
        keyboard.Key.page_down,
        keyboard.Key.page_up,
        keyboard.Key.down,
        keyboard.Key.up,
        keyboard.Key.left,
        keyboard.Key.right,
        keyboard.Key.home,
        keyboard.Key.end,
    ]
    
    def __init__(self, config, stats, session_manager, on_capture_callback=None, on_status_change=None, on_open_folder=None, on_open_settings=None):
        self.config = config
        self.stats = stats
        self.session_manager = session_manager
        self.on_capture_callback = on_capture_callback
        self.on_status_change = on_status_change
        self.on_open_folder = on_open_folder
        self.on_open_settings = on_open_settings
        self.keyboard_listener = None
        self.mouse_listener = None
        self.last_capture_time = 0
        self.last_window_title = ""
        self.screenshot_count = 0
        self.last_screenshot_hash = None  # For duplicate detection
        self.pending_capture = None  # Track pending capture timer
        self.capture_lock = threading.Lock()  # Thread safety
        self.recent_captures = []  # Store recent capture paths
        self.paused = False  # Pause/resume state
        self.document_capture_counts = {}  # Track captures per document
        self.accumulated_scroll = 0  # Track scroll distance
        self.folder_file_counts = {}  # Track files per folder
        
        # Manual hotkey tracking
        self.current_keys = set()
        
    def is_acrobat_active(self):
        """Check if Adobe Acrobat is the active window WITH a PDF open."""
        try:
            active_window = gw.getActiveWindow()
            if active_window:
                title = active_window.title
                # Check if it's Adobe Acrobat/Reader
                is_acrobat = any(acrobat_title in title for acrobat_title in self.ACROBAT_TITLES)
                if not is_acrobat:
                    return False, "", None
                
                # Check if an actual PDF is open
                # Adobe shows titles like "Document.pdf - Adobe Acrobat" or just "Document Name - Adobe Acrobat"
                # Reject if it's JUST the app name with no document
                just_app_names = ['Adobe Acrobat Reader', 'Adobe Acrobat', 'Adobe Acrobat Reader DC', 
                                  'Adobe Acrobat DC', 'Adobe Acrobat Pro DC', 'Adobe Acrobat Pro',
                                  'Home', 'Home - Adobe Acrobat Reader DC', 'Home - Adobe Acrobat DC']
                
                if title.strip() in just_app_names:
                    # No document open, just the app home screen
                    return False, "", None
                
                # If we get here, Acrobat is open with a document
                # The document might or might not have .pdf in the title (Adobe sometimes hides it)
                return True, title, active_window
        except Exception:
            pass
        return False, "", None
    
    def check_filters(self, window_title):
        """Check if the document passes whitelist/blacklist filters."""
        whitelist = self.config.get('filename_whitelist')
        blacklist = self.config.get('filename_blacklist')
        
        # If blacklist matches, reject
        if blacklist and matches_filter(window_title, blacklist):
            return False
        
        # If whitelist is set and doesn't match, reject
        if whitelist and not matches_filter(window_title, whitelist):
            return False
        
        return True
    
    def check_window_size(self, window):
        """Check if window meets minimum size requirements."""
        min_width = self.config.get('min_window_width')
        min_height = self.config.get('min_window_height')
        
        if window.width < min_width or window.height < min_height:
            return False
        return True
    
    def check_max_captures(self, doc_name):
        """Check if document has reached max captures limit."""
        max_captures = self.config.get('max_captures_per_document')
        if max_captures <= 0:
            return True  # No limit
        
        current_count = self.document_capture_counts.get(doc_name, 0)
        return current_count < max_captures
    
    def get_document_name(self, window_title):
        """Extract document name from window title."""
        # Acrobat typically shows: "Document.pdf - Adobe Acrobat Reader"
        for separator in [' - Adobe', ' – Adobe', ' — Adobe']:
            if separator in window_title:
                doc_name = window_title.split(separator)[0].strip()
                # Clean for filesystem
                doc_name = "".join(c for c in doc_name if c.isalnum() or c in (' ', '-', '_', '.')).strip()
                return doc_name[:50]  # Limit length
        return "Unknown Document"
    
    def get_image_hash(self, image_data):
        """Generate a hash of image data for duplicate detection."""
        return hashlib.md5(image_data).hexdigest()
    
    def get_document_area(self, window):
        """Try to estimate the document area within the Acrobat window."""
        # This is an approximation - Adobe Acrobat has toolbars at top and sides
        # We crop some pixels to try to get just the document
        left = window.left
        top = window.top
        width = window.width
        height = window.height
        
        # Approximate toolbar heights/widths (these vary by Acrobat version/config)
        top_offset = 120  # Top toolbar area
        bottom_offset = 30  # Bottom status bar
        left_offset = 15  # Left edge
        right_offset = 15  # Right edge
        
        # Adjust coordinates
        left += left_offset
        top += top_offset
        width -= (left_offset + right_offset)
        height -= (top_offset + bottom_offset)
        
        return left, top, width, height
    
    def capture_screenshot(self, manual=False):
        """Capture screenshot of the Acrobat window."""
        with self.capture_lock:
            if self.paused and not manual:
                return None
        
        is_active, window_title, window = self.is_acrobat_active()
        
        if not is_active or not window:
            if manual:
                logger.warning("Manual capture failed: Adobe Acrobat not active")
            return None
        
        # Check filters
        if not manual and not self.check_filters(window_title):
            logger.debug(f"Document filtered out: {window_title}")
            return None
        
        # Check window size
        if not self.check_window_size(window):
            logger.debug("Window too small to capture")
            return None
        
        doc_name = self.get_document_name(window_title)
        
        # Check max captures per document
        if not manual and not self.check_max_captures(doc_name):
            logger.debug(f"Max captures reached for: {doc_name}")
            return None
        
        # Check cooldown
        current_time = time.time()
        cooldown = self.config.get('capture_cooldown')
        if not manual and current_time - self.last_capture_time < cooldown:
            return None
        
        self.last_capture_time = current_time
        
        try:
            # Get window position and size
            if self.config.get('capture_document_only'):
                left, top, width, height = self.get_document_area(window)
            else:
                left = window.left
                top = window.top
                width = window.width
                height = window.height
            
            # Handle windows partially off-screen
            if left < 0:
                width += left
                left = 0
            if top < 0:
                height += top
                top = 0
            
            # Ensure we have valid dimensions
            if width <= 0 or height <= 0:
                logger.warning("Invalid window dimensions")
                return None
            
            # Capture the window region
            with mss.mss() as sct:
                monitor = {
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height
                }
                screenshot = sct.grab(monitor)
                
                # Check for duplicate screenshot (skip for manual captures)
                if not manual:
                    current_hash = self.get_image_hash(screenshot.rgb)
                    if current_hash == self.last_screenshot_hash:
                        logger.debug("Skipping duplicate screenshot")
                        return None
                    self.last_screenshot_hash = current_hash
                
                # Convert to PIL Image for processing
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                
                # Apply grayscale if enabled
                if self.config.get('grayscale_mode'):
                    img = img.convert('L').convert('RGB')
                
                # Resize if max dimensions are set
                max_width = self.config.get('max_image_width')
                max_height = self.config.get('max_image_height')
                if max_width > 0 or max_height > 0:
                    orig_width, orig_height = img.size
                    new_width, new_height = orig_width, orig_height
                    
                    if max_width > 0 and orig_width > max_width:
                        ratio = max_width / orig_width
                        new_width = max_width
                        new_height = int(orig_height * ratio)
                    
                    if max_height > 0 and new_height > max_height:
                        ratio = max_height / new_height
                        new_height = max_height
                        new_width = int(new_width * ratio)
                    
                    if new_width != orig_width or new_height != orig_height:
                        img = img.resize((new_width, new_height), Image.LANCZOS)
                
                # Add border if enabled
                if self.config.get('add_border'):
                    border_size = self.config.get('border_size')
                    border_color = self.config.get('border_color')
                    
                    # Parse hex color
                    try:
                        if border_color.startswith('#'):
                            border_color = border_color[1:]
                        r = int(border_color[0:2], 16)
                        g = int(border_color[2:4], 16)
                        b = int(border_color[4:6], 16)
                        color = (r, g, b)
                    except:
                        color = (255, 255, 255)
                    
                    new_width = img.width + (border_size * 2)
                    new_height = img.height + (border_size * 2)
                    bordered_img = Image.new('RGB', (new_width, new_height), color)
                    bordered_img.paste(img, (border_size, border_size))
                    img = bordered_img
                
                # Determine save location
                base_folder = Path(self.config.get('save_folder'))
                
                # Check for session folder
                session_folder = self.session_manager.get_session_folder()
                if session_folder:
                    save_folder = session_folder
                else:
                    save_folder = base_folder
                
                # Date-based organization
                if self.config.get('organize_by_date'):
                    date_format = self.config.get('date_folder_format')
                    now = datetime.now()
                    if date_format == 'monthly':
                        date_folder = now.strftime('%Y-%m')
                    elif date_format == 'weekly':
                        date_folder = now.strftime('%Y-W%W')
                    else:  # daily
                        date_folder = now.strftime('%Y-%m-%d')
                    save_folder = save_folder / date_folder
                
                # Document-based organization
                if self.config.get('organize_by_document'):
                    save_folder = save_folder / doc_name
                
                # Max files per folder
                max_files = self.config.get('max_files_per_folder')
                if max_files > 0:
                    folder_key = str(save_folder)
                    current_count = self.folder_file_counts.get(folder_key, 0)
                    if current_count >= max_files:
                        subfolder_num = (current_count // max_files) + 1
                        save_folder = save_folder / f"batch_{subfolder_num}"
                        folder_key = str(save_folder)
                        current_count = self.folder_file_counts.get(folder_key, 0)
                    self.folder_file_counts[folder_key] = current_count + 1
                
                save_folder.mkdir(parents=True, exist_ok=True)
                
                # Generate filename using template
                template = self.config.get('filename_template')
                base_filename = parse_filename_template(template, doc_name, self.config)
                
                self.screenshot_count += 1
                
                # Update document capture count
                self.document_capture_counts[doc_name] = self.document_capture_counts.get(doc_name, 0) + 1
                
                # Determine format and save
                img_format = self.config.get('image_format')
                
                if img_format == 'jpeg':
                    filename = f"{base_filename}.jpg"
                    filepath = save_folder / filename
                    img.save(str(filepath), "JPEG", quality=self.config.get('jpeg_quality'))
                elif img_format == 'webp':
                    filename = f"{base_filename}.webp"
                    filepath = save_folder / filename
                    img.save(str(filepath), "WEBP", quality=self.config.get('jpeg_quality'))
                else:  # png
                    filename = f"{base_filename}.png"
                    filepath = save_folder / filename
                    img.save(str(filepath), "PNG")
                
                logger.info(f"Screenshot saved: {filepath}")
                
                # Play sound if enabled
                if self.config.get('sound_enabled'):
                    play_capture_sound(self.config)
                
                # Record in recent captures (limit to 50)
                self.recent_captures.append({
                    'path': str(filepath),
                    'doc_name': doc_name,
                    'timestamp': datetime.now().isoformat()
                })
                if len(self.recent_captures) > 50:
                    self.recent_captures = self.recent_captures[-50:]
                
                # Add to session
                self.session_manager.add_capture(str(filepath))
                
                # Record statistics
                self.stats.record_capture(str(filepath), doc_name)
                
                if self.on_capture_callback:
                    self.on_capture_callback(str(filepath), doc_name)
                
                return str(filepath)
                
        except Exception as e:
            logger.error(f"Error capturing screenshot: {e}")
            return None
    
    def schedule_capture(self):
        """Schedule a screenshot capture with delay (non-blocking)."""
        # Cancel any pending capture to avoid duplicates
        if self.pending_capture:
            self.pending_capture.cancel()
        
        delay = self.config.get('capture_delay')
        self.pending_capture = threading.Timer(delay, self.capture_screenshot)
        self.pending_capture.daemon = True
        self.pending_capture.start()
    
    def check_manual_hotkey(self):
        """Check if manual capture hotkey is pressed."""
        ctrl_pressed = keyboard.Key.ctrl_l in self.current_keys or keyboard.Key.ctrl_r in self.current_keys
        shift_pressed = keyboard.Key.shift in self.current_keys or keyboard.Key.shift_r in self.current_keys
        s_pressed = keyboard.KeyCode.from_char('s') in self.current_keys
        
        return ctrl_pressed and shift_pressed and s_pressed
    
    def check_pause_hotkey(self):
        """Check if pause/resume hotkey is pressed."""
        ctrl_pressed = keyboard.Key.ctrl_l in self.current_keys or keyboard.Key.ctrl_r in self.current_keys
        shift_pressed = keyboard.Key.shift in self.current_keys or keyboard.Key.shift_r in self.current_keys
        p_pressed = keyboard.KeyCode.from_char('p') in self.current_keys
        
        return ctrl_pressed and shift_pressed and p_pressed
    
    def check_open_folder_hotkey(self):
        """Check if open folder hotkey is pressed."""
        ctrl_pressed = keyboard.Key.ctrl_l in self.current_keys or keyboard.Key.ctrl_r in self.current_keys
        shift_pressed = keyboard.Key.shift in self.current_keys or keyboard.Key.shift_r in self.current_keys
        o_pressed = keyboard.KeyCode.from_char('o') in self.current_keys
        
        return ctrl_pressed and shift_pressed and o_pressed
    
    def check_open_settings_hotkey(self):
        """Check if open settings hotkey is pressed."""
        ctrl_pressed = keyboard.Key.ctrl_l in self.current_keys or keyboard.Key.ctrl_r in self.current_keys
        shift_pressed = keyboard.Key.shift in self.current_keys or keyboard.Key.shift_r in self.current_keys
        comma_pressed = keyboard.KeyCode.from_char(',') in self.current_keys
        
        return ctrl_pressed and shift_pressed and comma_pressed
    
    def toggle_pause(self):
        """Toggle pause/resume state."""
        self.paused = not self.paused
        status = "paused" if self.paused else "resumed"
        logger.info(f"Capture {status}")
        if self.on_status_change:
            self.on_status_change('paused' if self.paused else 'enabled')
    
    def on_key_press(self, key):
        """Handle key press events (non-blocking)."""
        # Track current keys for hotkey detection
        self.current_keys.add(key)
        
        # Check for manual capture hotkey (Ctrl+Shift+S)
        if self.config.get('hotkey_enabled') and self.check_manual_hotkey():
            logger.info("Manual capture hotkey triggered")
            threading.Thread(target=lambda: self.capture_screenshot(manual=True), daemon=True).start()
            return
        
        # Check for pause/resume hotkey (Ctrl+Shift+P)
        if self.check_pause_hotkey():
            self.toggle_pause()
            return
        
        # Check for open folder hotkey (Ctrl+Shift+O)
        if self.check_open_folder_hotkey() and self.on_open_folder:
            threading.Thread(target=self.on_open_folder, daemon=True).start()
            return
        
        # Check for open settings hotkey (Ctrl+Shift+,)
        if self.check_open_settings_hotkey() and self.on_open_settings:
            threading.Thread(target=self.on_open_settings, daemon=True).start()
            return
        
        if not self.config.get('enabled') or self.paused:
            return
        
        is_active, _, _ = self.is_acrobat_active()
        if not is_active:
            return
        
        # Check if it's a navigation key
        if key in self.NAVIGATION_KEYS:
            self.schedule_capture()
    
    def on_key_release(self, key):
        """Handle key release events."""
        self.current_keys.discard(key)
    
    def on_scroll(self, x, y, dx, dy):
        """Handle mouse scroll events for PDF navigation."""
        if not self.config.get('enabled') or self.paused:
            return
        
        if not self.config.get('capture_on_scroll'):
            return
        
        is_active, _, _ = self.is_acrobat_active()
        if not is_active:
            return
        
        # Accumulate scroll distance
        scroll_amount = abs(dy) * 30  # Approximate pixels per scroll tick
        self.accumulated_scroll += scroll_amount
        
        # Check if we've scrolled enough
        min_scroll = self.config.get('min_scroll_distance')
        if self.accumulated_scroll >= min_scroll:
            self.accumulated_scroll = 0
            self.schedule_capture()
    
    def on_click(self, x, y, button, pressed):
        """Handle mouse click events."""
        if not pressed:  # Only on button press, not release
            return
        
        if not self.config.get('enabled') or self.paused:
            return
        
        if not self.config.get('capture_on_click'):
            return
        
        is_active, _, _ = self.is_acrobat_active()
        if not is_active:
            return
        
        self.schedule_capture()
    
    def start(self):
        """Start monitoring keyboard and mouse."""
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_key_press,
            on_release=self.on_key_release
        )
        self.keyboard_listener.start()
        
        # Monitor mouse scroll and optionally clicks
        self.mouse_listener = mouse.Listener(
            on_scroll=self.on_scroll,
            on_click=self.on_click
        )
        self.mouse_listener.start()
        
        logger.info("Monitoring started")
    
    def stop(self):
        """Stop monitoring."""
        if self.pending_capture:
            self.pending_capture.cancel()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.mouse_listener:
            self.mouse_listener.stop()
        logger.info("Monitoring stopped")


class FirstRunSetup:
    """First-run setup wizard shown on initial launch."""
    
    def __init__(self, config):
        self.config = config
        self.completed = False
    
    def show(self):
        """Show the first-run setup wizard."""
        import tkinter as tk
        from tkinter import filedialog, ttk
        
        self.window = tk.Tk()
        self.window.title("PDF Screenshot Tool - Welcome")
        self.window.geometry("550x720")
        self.window.resizable(False, False)
        
        # Apply dark theme
        self.window.configure(bg='#1a1a2e')
        
        # Try to set window icon
        try:
            icon_path = Path(__file__).parent.parent / 'assets' / 'icon.ico'
            if icon_path.exists():
                self.window.iconbitmap(str(icon_path))
        except Exception:
            pass
        
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        
        # Dark theme colors
        bg_color = '#1a1a2e'
        fg_color = '#e0e0e0'
        accent_color = '#4f46e5'
        entry_bg = '#16213e'
        
        style.configure('TFrame', background=bg_color)
        style.configure('TLabel', background=bg_color, foreground=fg_color)
        style.configure('TCheckbutton', background=bg_color, foreground=fg_color)
        style.configure('TButton', background=accent_color, foreground='white')
        style.configure('TEntry', fieldbackground=entry_bg, foreground=fg_color)
        style.configure('TLabelframe', background=bg_color, foreground=fg_color)
        style.configure('TLabelframe.Label', background=bg_color, foreground=accent_color, font=('Segoe UI', 10, 'bold'))
        
        style.configure('Title.TLabel', font=('Segoe UI', 18, 'bold'), background=bg_color, foreground='#ffffff')
        style.configure('Subtitle.TLabel', font=('Segoe UI', 11), background=bg_color, foreground='#a0a0a0')
        style.configure('Header.TLabel', font=('Segoe UI', 10, 'bold'), background=bg_color, foreground=accent_color)
        
        # Main frame
        main_frame = ttk.Frame(self.window, padding="30")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Welcome header
        ttk.Label(main_frame, text="👋 Welcome!", style='Title.TLabel').pack(pady=(0, 10))
        ttk.Label(
            main_frame, 
            text="Let's set up PDF Screenshot Tool.\nIt will run in the background and capture screenshots\nautomatically when you navigate PDF pages in Adobe Acrobat.",
            style='Subtitle.TLabel',
            justify=tk.CENTER
        ).pack(pady=(0, 30))
        
        # Settings section
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="15")
        settings_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Save folder
        ttk.Label(settings_frame, text="Save screenshots to:", style='Header.TLabel').pack(anchor=tk.W)
        
        folder_frame = ttk.Frame(settings_frame)
        folder_frame.pack(fill=tk.X, pady=(5, 15))
        
        self.folder_var = tk.StringVar(value=self.config.get('save_folder'))
        folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var, width=45)
        folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        browse_btn = ttk.Button(folder_frame, text="Browse...", command=self.browse_folder)
        browse_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # Options
        ttk.Label(settings_frame, text="Options:", style='Header.TLabel').pack(anchor=tk.W, pady=(10, 5))
        
        self.scroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            settings_frame, 
            text="Capture on mouse scroll (recommended for smooth scrolling)",
            variable=self.scroll_var
        ).pack(anchor=tk.W, pady=2)
        
        self.sound_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            settings_frame, 
            text="Play sound when screenshot is captured",
            variable=self.sound_var
        ).pack(anchor=tk.W, pady=2)
        
        self.notify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            settings_frame, 
            text="Show notification when screenshot is captured",
            variable=self.notify_var
        ).pack(anchor=tk.W, pady=2)
        
        self.startup_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            settings_frame, 
            text="Start automatically with Windows",
            variable=self.startup_var
        ).pack(anchor=tk.W, pady=2)
        
        # Info section
        info_frame = ttk.LabelFrame(main_frame, text="How to Use", padding="15")
        info_frame.pack(fill=tk.X, pady=(0, 20))
        
        steps = [
            "1. The app runs in the system tray (bottom-right, near clock)",
            "2. Open any PDF in Adobe Acrobat or Adobe Reader",
            "3. Navigate pages using Page Up/Down, arrows, or scroll",
            "4. Screenshots are captured automatically!",
            "",
            "Hotkeys:",
            "   • Ctrl+Shift+S - Manual capture",
            "   • Ctrl+Shift+P - Pause/Resume"
        ]
        
        for step in steps:
            ttk.Label(info_frame, text=step, justify=tk.LEFT).pack(anchor=tk.W, pady=1)
        
        # Big Start Button
        start_btn = tk.Button(
            main_frame, 
            text="  ▶  Start PDF Screenshot Tool  ", 
            command=self.finish_setup,
            font=('Segoe UI', 12, 'bold'),
            bg='#4f46e5',
            fg='white',
            padx=30,
            pady=12,
            cursor='hand2',
            relief=tk.FLAT,
            activebackground='#4338ca',
            activeforeground='white'
        )
        start_btn.pack(pady=(25, 10))
        
        # Center window
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'+{x}+{y}')
        
        # Make it stay on top
        self.window.attributes('-topmost', True)
        self.window.focus_force()
        
        self.window.protocol("WM_DELETE_WINDOW", self.finish_setup)
        self.window.mainloop()
        
        return self.completed
    
    def browse_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(initialdir=self.folder_var.get())
        if folder:
            self.folder_var.set(folder)
    
    def finish_setup(self):
        # Save settings
        self.config.set('save_folder', self.folder_var.get())
        self.config.set('capture_on_scroll', self.scroll_var.get())
        self.config.set('sound_enabled', self.sound_var.get())
        self.config.set('show_notifications', self.notify_var.get())
        
        # Handle startup setting
        if self.startup_var.get():
            set_startup_registry(True)
        self.config.set('start_with_windows', self.startup_var.get())
        
        self.completed = True
        self.window.destroy()
        logger.info("First-run setup completed")


class RecentCapturesWindow:
    """Window showing recent captures with preview."""
    
    def __init__(self, monitor, config):
        self.monitor = monitor
        self.config = config
        self.window = None
    
    def show(self):
        """Show the recent captures window."""
        import tkinter as tk
        from tkinter import ttk
        
        if self.window is not None:
            try:
                self.window.lift()
                self.window.focus_force()
                return
            except tk.TclError:
                self.window = None
        
        self.window = tk.Tk()
        self.window.title("Recent Captures")
        self.window.geometry("700x500")
        
        # Apply dark theme
        bg_color = '#1a1a2e' if self.config.get('dark_mode') else '#ffffff'
        fg_color = '#e0e0e0' if self.config.get('dark_mode') else '#1a1a2e'
        
        self.window.configure(bg=bg_color)
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=bg_color)
        style.configure('TLabel', background=bg_color, foreground=fg_color)
        style.configure('TButton', padding=5)
        
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main_frame, text="Recent Captures", font=('Segoe UI', 14, 'bold')).pack(pady=(0, 15))
        
        # Listbox with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(
            list_frame, 
            yscrollcommand=scrollbar.set,
            font=('Segoe UI', 10),
            bg='#16213e' if self.config.get('dark_mode') else '#f5f5f5',
            fg=fg_color,
            selectbackground='#4f46e5',
            selectforeground='white',
            height=15
        )
        self.listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Populate list
        for capture in reversed(self.monitor.recent_captures):
            timestamp = datetime.fromisoformat(capture['timestamp']).strftime("%Y-%m-%d %H:%M:%S")
            self.listbox.insert(tk.END, f"{timestamp} - {capture['doc_name']}")
        
        if not self.monitor.recent_captures:
            self.listbox.insert(tk.END, "No captures yet")
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        
        open_btn = ttk.Button(btn_frame, text="Open Selected", command=self.open_selected)
        open_btn.pack(side=tk.LEFT)
        
        open_folder_btn = ttk.Button(btn_frame, text="Open Folder", command=self.open_folder)
        open_folder_btn.pack(side=tk.LEFT, padx=10)
        
        close_btn = ttk.Button(btn_frame, text="Close", command=self.close)
        close_btn.pack(side=tk.RIGHT)
        
        # Center window
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (350)
        y = (self.window.winfo_screenheight() // 2) - (250)
        self.window.geometry(f'+{x}+{y}')
        
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.mainloop()
    
    def open_selected(self):
        import subprocess
        selection = self.listbox.curselection()
        if selection:
            # Reverse index since list is reversed
            idx = len(self.monitor.recent_captures) - 1 - selection[0]
            if 0 <= idx < len(self.monitor.recent_captures):
                filepath = self.monitor.recent_captures[idx]['path']
                if Path(filepath).exists():
                    subprocess.Popen(f'explorer /select,"{filepath}"')
    
    def open_folder(self):
        import subprocess
        folder = self.config.get('save_folder')
        subprocess.Popen(f'explorer "{folder}"')
    
    def close(self):
        if self.window:
            self.window.destroy()
            self.window = None


class StatisticsWindow:
    """Window showing capture statistics."""
    
    def __init__(self, stats, config):
        self.stats = stats
        self.config = config
        self.window = None
    
    def show(self):
        """Show the statistics window."""
        import tkinter as tk
        from tkinter import ttk
        
        if self.window is not None:
            try:
                self.window.lift()
                self.window.focus_force()
                return
            except tk.TclError:
                self.window = None
        
        self.window = tk.Tk()
        self.window.title("Statistics")
        self.window.geometry("400x350")
        self.window.resizable(False, False)
        
        # Apply dark theme
        bg_color = '#1a1a2e' if self.config.get('dark_mode') else '#ffffff'
        fg_color = '#e0e0e0' if self.config.get('dark_mode') else '#1a1a2e'
        accent_color = '#4f46e5'
        
        self.window.configure(bg=bg_color)
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=bg_color)
        style.configure('TLabel', background=bg_color, foreground=fg_color)
        style.configure('Title.TLabel', font=('Segoe UI', 14, 'bold'), background=bg_color, foreground='#ffffff')
        style.configure('Stat.TLabel', font=('Segoe UI', 24, 'bold'), background=bg_color, foreground=accent_color)
        style.configure('StatLabel.TLabel', font=('Segoe UI', 9), background=bg_color, foreground='#888888')
        
        main_frame = ttk.Frame(self.window, padding="30")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="📊 Statistics", style='Title.TLabel').pack(pady=(0, 20))
        
        summary = self.stats.get_summary()
        
        # Stats grid
        stats_frame = ttk.Frame(main_frame)
        stats_frame.pack(fill=tk.X)
        
        stats_data = [
            ('Total Captures', str(summary['total_captures'])),
            ('This Session', str(summary['session_captures'])),
            ('Total Size', f"{summary['total_size_mb']} MB"),
            ('Documents', str(summary['documents_count'])),
            ('Days Active', str(summary['days_active'])),
            ('Avg/Day', str(summary['avg_per_day'])),
        ]
        
        for i, (label, value) in enumerate(stats_data):
            row = i // 2
            col = i % 2
            
            stat_box = ttk.Frame(stats_frame)
            stat_box.grid(row=row, column=col, padx=20, pady=10, sticky='w')
            
            ttk.Label(stat_box, text=value, style='Stat.TLabel').pack(anchor='w')
            ttk.Label(stat_box, text=label, style='StatLabel.TLabel').pack(anchor='w')
        
        # Close button
        close_btn = ttk.Button(main_frame, text="Close", command=self.close)
        close_btn.pack(pady=(30, 0))
        
        # Center window
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (200)
        y = (self.window.winfo_screenheight() // 2) - (175)
        self.window.geometry(f'+{x}+{y}')
        
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.mainloop()
    
    def close(self):
        if self.window:
            self.window.destroy()
            self.window = None


class BatchActionsWindow:
    """Window for batch actions on screenshots."""
    
    def __init__(self, config):
        self.config = config
        self.window = None
    
    def show(self):
        """Show the batch actions window."""
        import tkinter as tk
        from tkinter import ttk, messagebox, filedialog
        
        if self.window is not None:
            try:
                self.window.lift()
                self.window.focus_force()
                return
            except tk.TclError:
                self.window = None
        
        self.window = tk.Tk()
        self.window.title("Batch Actions")
        self.window.geometry("450x400")
        self.window.resizable(False, False)
        
        # Apply dark theme
        bg_color = '#1a1a2e' if self.config.get('dark_mode') else '#ffffff'
        fg_color = '#e0e0e0' if self.config.get('dark_mode') else '#1a1a2e'
        
        self.window.configure(bg=bg_color)
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=bg_color)
        style.configure('TLabel', background=bg_color, foreground=fg_color)
        style.configure('TLabelframe', background=bg_color, foreground=fg_color)
        style.configure('TLabelframe.Label', background=bg_color, foreground='#4f46e5', font=('Segoe UI', 10, 'bold'))
        style.configure('Title.TLabel', font=('Segoe UI', 14, 'bold'), background=bg_color, foreground='#ffffff')
        style.configure('Danger.TButton', background='#ef4444')
        
        main_frame = ttk.Frame(self.window, padding="30")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="🗂️ Batch Actions", style='Title.TLabel').pack(pady=(0, 20))
        
        # Export section
        export_frame = ttk.LabelFrame(main_frame, text="Export", padding="15")
        export_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(export_frame, text="Export All to ZIP", command=self.export_zip).pack(fill=tk.X, pady=5)
        ttk.Button(export_frame, text="Export All to PDF", command=self.export_pdf).pack(fill=tk.X, pady=5)
        
        # Cleanup section
        cleanup_frame = ttk.LabelFrame(main_frame, text="Cleanup", padding="15")
        cleanup_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(cleanup_frame, text="Delete Old Screenshots (30+ days)", command=self.delete_old).pack(fill=tk.X, pady=5)
        
        delete_btn = tk.Button(
            cleanup_frame, 
            text="Delete ALL Screenshots", 
            command=self.delete_all,
            bg='#ef4444',
            fg='white',
            font=('Segoe UI', 10),
            relief=tk.FLAT,
            cursor='hand2'
        )
        delete_btn.pack(fill=tk.X, pady=5)
        
        # Status
        self.status_var = tk.StringVar(value="")
        ttk.Label(main_frame, textvariable=self.status_var, font=('Segoe UI', 9)).pack(pady=10)
        
        # Close button
        ttk.Button(main_frame, text="Close", command=self.close).pack(pady=(10, 0))
        
        # Center window
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (225)
        y = (self.window.winfo_screenheight() // 2) - (200)
        self.window.geometry(f'+{x}+{y}')
        
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.mainloop()
    
    def export_zip(self):
        from tkinter import filedialog, messagebox
        
        folder = Path(self.config.get('save_folder'))
        if not folder.exists():
            messagebox.showerror("Error", "Screenshot folder does not exist")
            return
        
        # Get list of images
        images = list(folder.rglob('*.png')) + list(folder.rglob('*.jpg')) + list(folder.rglob('*.jpeg'))
        
        if not images:
            messagebox.showinfo("Info", "No screenshots to export")
            return
        
        # Ask for save location
        save_path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP files", "*.zip")],
            initialfile=f"pdf_screenshots_{datetime.now().strftime('%Y%m%d')}.zip"
        )
        
        if not save_path:
            return
        
        try:
            self.status_var.set("Exporting...")
            self.window.update()
            
            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for img in images:
                    arcname = img.relative_to(folder)
                    zf.write(img, arcname)
            
            self.status_var.set(f"✓ Exported {len(images)} files to ZIP")
            messagebox.showinfo("Success", f"Exported {len(images)} screenshots to:\n{save_path}")
        except Exception as e:
            self.status_var.set(f"Error: {e}")
            messagebox.showerror("Error", f"Export failed: {e}")
    
    def export_pdf(self):
        from tkinter import filedialog, messagebox
        
        folder = Path(self.config.get('save_folder'))
        if not folder.exists():
            messagebox.showerror("Error", "Screenshot folder does not exist")
            return
        
        # Get list of images
        images = sorted(list(folder.rglob('*.png')) + list(folder.rglob('*.jpg')) + list(folder.rglob('*.jpeg')))
        
        if not images:
            messagebox.showinfo("Info", "No screenshots to export")
            return
        
        # Ask for save location
        save_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"pdf_screenshots_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
        
        if not save_path:
            return
        
        try:
            self.status_var.set("Creating PDF...")
            self.window.update()
            
            # Convert images to PDF
            img_list = []
            for img_path in images:
                img = Image.open(img_path)
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                img_list.append(img)
            
            if img_list:
                img_list[0].save(save_path, save_all=True, append_images=img_list[1:])
            
            self.status_var.set(f"✓ Exported {len(images)} images to PDF")
            messagebox.showinfo("Success", f"Exported {len(images)} screenshots to:\n{save_path}")
        except Exception as e:
            self.status_var.set(f"Error: {e}")
            messagebox.showerror("Error", f"Export failed: {e}")
    
    def delete_old(self):
        from tkinter import messagebox
        
        folder = self.config.get('save_folder')
        
        if not messagebox.askyesno("Confirm", "Delete all screenshots older than 30 days?"):
            return
        
        try:
            self.status_var.set("Cleaning up...")
            self.window.update()
            
            deleted = cleanup_old_screenshots(folder, 30)
            
            self.status_var.set(f"✓ Deleted {deleted} old screenshots")
            messagebox.showinfo("Success", f"Deleted {deleted} screenshots older than 30 days")
        except Exception as e:
            self.status_var.set(f"Error: {e}")
            messagebox.showerror("Error", f"Cleanup failed: {e}")
    
    def delete_all(self):
        from tkinter import messagebox
        
        folder = Path(self.config.get('save_folder'))
        
        if not messagebox.askyesno("⚠️ Warning", "This will DELETE ALL screenshots!\n\nAre you sure?"):
            return
        
        if not messagebox.askyesno("Final Confirmation", "This cannot be undone!\n\nProceed?"):
            return
        
        try:
            self.status_var.set("Deleting all...")
            self.window.update()
            
            count = 0
            for file in folder.rglob('*'):
                if file.is_file() and file.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                    file.unlink()
                    count += 1
            
            # Remove empty directories
            for dir_path in sorted(folder.rglob('*'), reverse=True):
                if dir_path.is_dir():
                    try:
                        dir_path.rmdir()
                    except OSError:
                        pass  # Directory not empty
            
            self.status_var.set(f"✓ Deleted {count} screenshots")
            messagebox.showinfo("Success", f"Deleted {count} screenshots")
        except Exception as e:
            self.status_var.set(f"Error: {e}")
            messagebox.showerror("Error", f"Delete failed: {e}")
    
    def close(self):
        if self.window:
            self.window.destroy()
            self.window = None


class SettingsWindow:
    """Settings window using tkinter."""
    
    def __init__(self, config, monitor, stats):
        self.config = config
        self.monitor = monitor
        self.stats = stats
        self.window = None
    
    def show(self):
        """Show the settings window."""
        import tkinter as tk
        from tkinter import filedialog, ttk
        
        if self.window is not None:
            try:
                self.window.lift()
                self.window.focus_force()
                return
            except tk.TclError:
                self.window = None
        
        self.window = tk.Tk()
        self.window.title("PDF Screenshot Tool - Settings")
        self.window.geometry("580x750")
        self.window.resizable(False, False)
        
        # Apply theme
        is_dark = self.config.get('dark_mode')
        bg_color = '#1a1a2e' if is_dark else '#ffffff'
        fg_color = '#e0e0e0' if is_dark else '#1a1a2e'
        entry_bg = '#16213e' if is_dark else '#f5f5f5'
        accent_color = '#4f46e5'
        
        self.window.configure(bg=bg_color)
        
        # Try to set window icon
        try:
            icon_path = Path(__file__).parent.parent / 'assets' / 'icon.ico'
            if icon_path.exists():
                self.window.iconbitmap(str(icon_path))
        except Exception:
            pass
        
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure('TFrame', background=bg_color)
        style.configure('TLabel', background=bg_color, foreground=fg_color, padding=5)
        style.configure('TButton', padding=5)
        style.configure('TCheckbutton', background=bg_color, foreground=fg_color, padding=5)
        style.configure('TRadiobutton', background=bg_color, foreground=fg_color)
        style.configure('TSpinbox', fieldbackground=entry_bg, foreground=fg_color)
        style.configure('TEntry', fieldbackground=entry_bg, foreground=fg_color)
        style.configure('Header.TLabel', font=('Segoe UI', 10, 'bold'), background=bg_color, foreground=accent_color)
        style.configure('Title.TLabel', font=('Segoe UI', 16, 'bold'), background=bg_color, foreground='#ffffff' if is_dark else '#1a1a2e')
        
        # Create scrollable canvas
        canvas = tk.Canvas(self.window, bg=bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.window, orient="vertical", command=canvas.yview)
        
        main_frame = ttk.Frame(canvas, padding="20")
        
        main_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=main_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Enable mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="PDF Screenshot Tool", style='Title.TLabel')
        title_label.pack(pady=(0, 20))
        
        # === Capture Settings ===
        ttk.Label(main_frame, text="Capture Settings", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # Enable/Disable
        self.enabled_var = tk.BooleanVar(value=self.config.get('enabled'))
        enabled_check = ttk.Checkbutton(
            main_frame, 
            text="Enable automatic screenshots",
            variable=self.enabled_var,
            command=self.toggle_enabled
        )
        enabled_check.pack(anchor=tk.W, pady=2)
        
        # Capture on mouse scroll
        self.scroll_var = tk.BooleanVar(value=self.config.get('capture_on_scroll'))
        scroll_check = ttk.Checkbutton(
            main_frame, 
            text="Capture on mouse scroll",
            variable=self.scroll_var
        )
        scroll_check.pack(anchor=tk.W, pady=2)
        
        # Manual hotkey
        self.hotkey_var = tk.BooleanVar(value=self.config.get('hotkey_enabled'))
        hotkey_check = ttk.Checkbutton(
            main_frame, 
            text="Enable manual capture hotkey (Ctrl+Shift+S)",
            variable=self.hotkey_var
        )
        hotkey_check.pack(anchor=tk.W, pady=2)
        
        # Capture document area only
        self.doc_only_var = tk.BooleanVar(value=self.config.get('capture_document_only'))
        doc_only_check = ttk.Checkbutton(
            main_frame, 
            text="Capture document area only (excludes toolbars)",
            variable=self.doc_only_var
        )
        doc_only_check.pack(anchor=tk.W, pady=2)
        
        # Show notifications
        self.notify_var = tk.BooleanVar(value=self.config.get('show_notifications'))
        notify_check = ttk.Checkbutton(
            main_frame, 
            text="Show notification when screenshot is captured",
            variable=self.notify_var
        )
        notify_check.pack(anchor=tk.W, pady=2)
        
        # Sound feedback
        self.sound_var = tk.BooleanVar(value=self.config.get('sound_enabled'))
        sound_check = ttk.Checkbutton(
            main_frame, 
            text="Play sound when screenshot is captured",
            variable=self.sound_var
        )
        sound_check.pack(anchor=tk.W, pady=2)
        
        # Capture delay
        delay_frame = ttk.Frame(main_frame)
        delay_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(delay_frame, text="Capture delay:").pack(side=tk.LEFT)
        
        self.delay_var = tk.StringVar(value=str(self.config.get('capture_delay')))
        delay_spin = ttk.Spinbox(
            delay_frame, 
            from_=0.1, 
            to=2.0, 
            increment=0.1,
            textvariable=self.delay_var,
            width=8
        )
        delay_spin.pack(side=tk.LEFT, padx=(10, 5))
        ttk.Label(delay_frame, text="seconds").pack(side=tk.LEFT)
        
        # === Save Settings ===
        ttk.Label(main_frame, text="Save Settings", style='Header.TLabel').pack(anchor=tk.W, pady=(15, 0))
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # Save folder
        ttk.Label(main_frame, text="Save folder:").pack(anchor=tk.W)
        
        folder_input_frame = ttk.Frame(main_frame)
        folder_input_frame.pack(fill=tk.X, pady=5)
        
        self.folder_var = tk.StringVar(value=self.config.get('save_folder'))
        folder_entry = ttk.Entry(folder_input_frame, textvariable=self.folder_var, width=50)
        folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        browse_btn = ttk.Button(folder_input_frame, text="Browse...", command=self.browse_folder)
        browse_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # Organize by document
        self.organize_var = tk.BooleanVar(value=self.config.get('organize_by_document'))
        organize_check = ttk.Checkbutton(
            main_frame, 
            text="Create subfolder for each document",
            variable=self.organize_var
        )
        organize_check.pack(anchor=tk.W, pady=2)
        
        # Image format
        format_frame = ttk.Frame(main_frame)
        format_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(format_frame, text="Image format:").pack(side=tk.LEFT)
        
        self.format_var = tk.StringVar(value=self.config.get('image_format'))
        png_radio = ttk.Radiobutton(format_frame, text="PNG (lossless)", variable=self.format_var, value='png')
        png_radio.pack(side=tk.LEFT, padx=(10, 5))
        jpeg_radio = ttk.Radiobutton(format_frame, text="JPEG (smaller)", variable=self.format_var, value='jpeg')
        jpeg_radio.pack(side=tk.LEFT, padx=5)
        webp_radio = ttk.Radiobutton(format_frame, text="WebP (modern)", variable=self.format_var, value='webp')
        webp_radio.pack(side=tk.LEFT)
        
        # Quality (for JPEG/WebP)
        quality_frame = ttk.Frame(main_frame)
        quality_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(quality_frame, text="Quality (JPEG/WebP):").pack(side=tk.LEFT)
        
        self.quality_var = tk.StringVar(value=str(self.config.get('jpeg_quality')))
        quality_spin = ttk.Spinbox(
            quality_frame, 
            from_=50, 
            to=100, 
            increment=5,
            textvariable=self.quality_var,
            width=8
        )
        quality_spin.pack(side=tk.LEFT, padx=(10, 5))
        ttk.Label(quality_frame, text="%").pack(side=tk.LEFT)
        
        # === Auto Cleanup ===
        ttk.Label(main_frame, text="Auto Cleanup", style='Header.TLabel').pack(anchor=tk.W, pady=(15, 0))
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        self.cleanup_var = tk.BooleanVar(value=self.config.get('auto_cleanup_enabled'))
        cleanup_check = ttk.Checkbutton(
            main_frame, 
            text="Automatically delete old screenshots",
            variable=self.cleanup_var
        )
        cleanup_check.pack(anchor=tk.W, pady=2)
        
        cleanup_days_frame = ttk.Frame(main_frame)
        cleanup_days_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(cleanup_days_frame, text="Delete screenshots older than:").pack(side=tk.LEFT)
        
        self.cleanup_days_var = tk.StringVar(value=str(self.config.get('auto_cleanup_days')))
        cleanup_days_spin = ttk.Spinbox(
            cleanup_days_frame, 
            from_=7, 
            to=365, 
            increment=7,
            textvariable=self.cleanup_days_var,
            width=8
        )
        cleanup_days_spin.pack(side=tk.LEFT, padx=(10, 5))
        ttk.Label(cleanup_days_frame, text="days").pack(side=tk.LEFT)
        
        # === System Settings ===
        ttk.Label(main_frame, text="System", style='Header.TLabel').pack(anchor=tk.W, pady=(15, 0))
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # Start with Windows
        self.startup_var = tk.BooleanVar(value=is_startup_enabled())
        startup_check = ttk.Checkbutton(
            main_frame, 
            text="Start automatically with Windows",
            variable=self.startup_var
        )
        startup_check.pack(anchor=tk.W, pady=2)
        
        # Dark mode
        self.dark_var = tk.BooleanVar(value=self.config.get('dark_mode'))
        dark_check = ttk.Checkbutton(
            main_frame, 
            text="Dark mode (requires restart)",
            variable=self.dark_var
        )
        dark_check.pack(anchor=tk.W, pady=2)
        
        # Status
        summary = self.stats.get_summary()
        self.status_label = ttk.Label(
            main_frame, 
            text=f"Session: {summary['session_captures']} | Total: {summary['total_captures']} | Size: {summary['total_size_mb']} MB",
            font=('Segoe UI', 10)
        )
        self.status_label.pack(pady=15)
        
        # Buttons row 1
        btn_frame1 = ttk.Frame(main_frame)
        btn_frame1.pack(fill=tk.X, pady=5)
        
        save_btn = ttk.Button(btn_frame1, text="💾 Save Settings", command=self.save_settings)
        save_btn.pack(side=tk.LEFT)
        
        open_folder_btn = ttk.Button(btn_frame1, text="📂 Open Folder", command=self.open_folder)
        open_folder_btn.pack(side=tk.LEFT, padx=10)
        
        # Buttons row 2
        btn_frame2 = ttk.Frame(main_frame)
        btn_frame2.pack(fill=tk.X, pady=5)
        
        stats_btn = ttk.Button(btn_frame2, text="📊 Statistics", command=self.show_stats)
        stats_btn.pack(side=tk.LEFT)
        
        recent_btn = ttk.Button(btn_frame2, text="🖼️ Recent", command=self.show_recent)
        recent_btn.pack(side=tk.LEFT, padx=10)
        
        batch_btn = ttk.Button(btn_frame2, text="🗂️ Batch Actions", command=self.show_batch)
        batch_btn.pack(side=tk.LEFT)
        
        # Buttons row 3
        btn_frame3 = ttk.Frame(main_frame)
        btn_frame3.pack(fill=tk.X, pady=5)
        
        open_log_btn = ttk.Button(btn_frame3, text="📝 View Log", command=self.open_log)
        open_log_btn.pack(side=tk.LEFT)
        
        advanced_btn = ttk.Button(btn_frame3, text="⚙️ Advanced", command=self.show_advanced)
        advanced_btn.pack(side=tk.LEFT, padx=10)
        
        close_btn = ttk.Button(btn_frame3, text="Close", command=self.close)
        close_btn.pack(side=tk.RIGHT)
        
        # Center window
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'+{x}+{y}')
        
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.mainloop()
    
    def toggle_enabled(self):
        self.config.set('enabled', self.enabled_var.get())
    
    def browse_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(initialdir=self.folder_var.get())
        if folder:
            self.folder_var.set(folder)
    
    def save_settings(self):
        self.config.set('save_folder', self.folder_var.get())
        self.config.set('capture_delay', float(self.delay_var.get()))
        self.config.set('enabled', self.enabled_var.get())
        self.config.set('capture_on_scroll', self.scroll_var.get())
        self.config.set('hotkey_enabled', self.hotkey_var.get())
        self.config.set('show_notifications', self.notify_var.get())
        self.config.set('sound_enabled', self.sound_var.get())
        self.config.set('capture_document_only', self.doc_only_var.get())
        self.config.set('organize_by_document', self.organize_var.get())
        self.config.set('image_format', self.format_var.get())
        self.config.set('jpeg_quality', int(self.quality_var.get()))
        self.config.set('auto_cleanup_enabled', self.cleanup_var.get())
        self.config.set('auto_cleanup_days', int(self.cleanup_days_var.get()))
        self.config.set('dark_mode', self.dark_var.get())
        
        # Handle startup setting
        set_startup_registry(self.startup_var.get())
        self.config.set('start_with_windows', self.startup_var.get())
        
        # Update status
        self.status_label.config(text="✓ Settings saved!")
        self.window.after(2000, lambda: self.status_label.config(
            text=f"Session: {self.stats.get_summary()['session_captures']} | Total: {self.stats.get_summary()['total_captures']}"
        ))
    
    def open_folder(self):
        import subprocess
        folder = self.config.get('save_folder')
        Path(folder).mkdir(parents=True, exist_ok=True)
        subprocess.Popen(f'explorer "{folder}"')
    
    def open_log(self):
        import subprocess
        subprocess.Popen(f'notepad "{LOG_FILE}"')
    
    def show_stats(self):
        stats_window = StatisticsWindow(self.stats, self.config)
        threading.Thread(target=stats_window.show, daemon=True).start()
    
    def show_recent(self):
        recent_window = RecentCapturesWindow(self.monitor, self.config)
        threading.Thread(target=recent_window.show, daemon=True).start()
    
    def show_batch(self):
        batch_window = BatchActionsWindow(self.config)
        threading.Thread(target=batch_window.show, daemon=True).start()
    
    def show_advanced(self):
        advanced_window = AdvancedSettingsWindow(self.config)
        threading.Thread(target=advanced_window.show, daemon=True).start()
    
    def close(self):
        if self.window:
            self.window.destroy()
            self.window = None


class AdvancedSettingsWindow:
    """Advanced settings window with all detailed options."""
    
    def __init__(self, config):
        self.config = config
        self.window = None
    
    def show(self):
        """Show the advanced settings window."""
        import tkinter as tk
        from tkinter import ttk, filedialog
        
        if self.window is not None:
            try:
                self.window.lift()
                self.window.focus_force()
                return
            except tk.TclError:
                self.window = None
        
        self.window = tk.Tk()
        self.window.title("Advanced Settings")
        self.window.geometry("650x700")
        
        # Apply theme
        is_dark = self.config.get('dark_mode')
        bg_color = '#1a1a2e' if is_dark else '#ffffff'
        fg_color = '#e0e0e0' if is_dark else '#1a1a2e'
        entry_bg = '#16213e' if is_dark else '#f5f5f5'
        accent_color = '#4f46e5'
        
        self.window.configure(bg=bg_color)
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=bg_color)
        style.configure('TLabel', background=bg_color, foreground=fg_color)
        style.configure('TCheckbutton', background=bg_color, foreground=fg_color)
        style.configure('TEntry', fieldbackground=entry_bg)
        style.configure('Header.TLabel', font=('Segoe UI', 10, 'bold'), background=bg_color, foreground=accent_color)
        style.configure('TNotebook', background=bg_color)
        style.configure('TNotebook.Tab', padding=[10, 5])
        
        # Create notebook (tabs)
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # === Capture Tab ===
        capture_frame = ttk.Frame(notebook, padding=15)
        notebook.add(capture_frame, text="Capture")
        
        ttk.Label(capture_frame, text="Capture Behavior", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Separator(capture_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        self.click_var = tk.BooleanVar(value=self.config.get('capture_on_click'))
        ttk.Checkbutton(capture_frame, text="Capture on mouse click in Acrobat", variable=self.click_var).pack(anchor=tk.W)
        
        # Cooldown
        cooldown_frame = ttk.Frame(capture_frame)
        cooldown_frame.pack(fill=tk.X, pady=5)
        ttk.Label(cooldown_frame, text="Capture cooldown:").pack(side=tk.LEFT)
        self.cooldown_var = tk.StringVar(value=str(self.config.get('capture_cooldown')))
        ttk.Spinbox(cooldown_frame, from_=0.1, to=5.0, increment=0.1, textvariable=self.cooldown_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(cooldown_frame, text="seconds").pack(side=tk.LEFT)
        
        # Min scroll distance
        scroll_frame = ttk.Frame(capture_frame)
        scroll_frame.pack(fill=tk.X, pady=5)
        ttk.Label(scroll_frame, text="Min scroll distance:").pack(side=tk.LEFT)
        self.min_scroll_var = tk.StringVar(value=str(self.config.get('min_scroll_distance')))
        ttk.Spinbox(scroll_frame, from_=10, to=200, increment=10, textvariable=self.min_scroll_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(scroll_frame, text="pixels").pack(side=tk.LEFT)
        
        # Max captures per document
        max_frame = ttk.Frame(capture_frame)
        max_frame.pack(fill=tk.X, pady=5)
        ttk.Label(max_frame, text="Max captures per document:").pack(side=tk.LEFT)
        self.max_captures_var = tk.StringVar(value=str(self.config.get('max_captures_per_document')))
        ttk.Spinbox(max_frame, from_=0, to=1000, increment=10, textvariable=self.max_captures_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(max_frame, text="(0 = unlimited)").pack(side=tk.LEFT)
        
        # === Image Tab ===
        image_frame = ttk.Frame(notebook, padding=15)
        notebook.add(image_frame, text="Image")
        
        ttk.Label(image_frame, text="Image Processing", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Separator(image_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        self.grayscale_var = tk.BooleanVar(value=self.config.get('grayscale_mode'))
        ttk.Checkbutton(image_frame, text="Convert to grayscale (smaller files)", variable=self.grayscale_var).pack(anchor=tk.W)
        
        self.border_var = tk.BooleanVar(value=self.config.get('add_border'))
        ttk.Checkbutton(image_frame, text="Add border around captures", variable=self.border_var).pack(anchor=tk.W)
        
        border_size_frame = ttk.Frame(image_frame)
        border_size_frame.pack(fill=tk.X, pady=5)
        ttk.Label(border_size_frame, text="Border size:").pack(side=tk.LEFT)
        self.border_size_var = tk.StringVar(value=str(self.config.get('border_size')))
        ttk.Spinbox(border_size_frame, from_=1, to=50, increment=1, textvariable=self.border_size_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(border_size_frame, text="pixels").pack(side=tk.LEFT)
        
        border_color_frame = ttk.Frame(image_frame)
        border_color_frame.pack(fill=tk.X, pady=5)
        ttk.Label(border_color_frame, text="Border color:").pack(side=tk.LEFT)
        self.border_color_var = tk.StringVar(value=self.config.get('border_color'))
        ttk.Entry(border_color_frame, textvariable=self.border_color_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(border_color_frame, text="(hex, e.g. #ffffff)").pack(side=tk.LEFT)
        
        ttk.Label(image_frame, text="Max Dimensions (0 = no limit)", style='Header.TLabel').pack(anchor=tk.W, pady=(15, 0))
        ttk.Separator(image_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        max_width_frame = ttk.Frame(image_frame)
        max_width_frame.pack(fill=tk.X, pady=5)
        ttk.Label(max_width_frame, text="Max width:").pack(side=tk.LEFT)
        self.max_width_var = tk.StringVar(value=str(self.config.get('max_image_width')))
        ttk.Spinbox(max_width_frame, from_=0, to=4000, increment=100, textvariable=self.max_width_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(max_width_frame, text="pixels").pack(side=tk.LEFT)
        
        max_height_frame = ttk.Frame(image_frame)
        max_height_frame.pack(fill=tk.X, pady=5)
        ttk.Label(max_height_frame, text="Max height:").pack(side=tk.LEFT)
        self.max_height_var = tk.StringVar(value=str(self.config.get('max_image_height')))
        ttk.Spinbox(max_height_frame, from_=0, to=4000, increment=100, textvariable=self.max_height_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(max_height_frame, text="pixels").pack(side=tk.LEFT)
        
        # === Files Tab ===
        files_frame = ttk.Frame(notebook, padding=15)
        notebook.add(files_frame, text="Files")
        
        ttk.Label(files_frame, text="File Organization", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Separator(files_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        self.date_org_var = tk.BooleanVar(value=self.config.get('organize_by_date'))
        ttk.Checkbutton(files_frame, text="Organize by date", variable=self.date_org_var).pack(anchor=tk.W)
        
        date_format_frame = ttk.Frame(files_frame)
        date_format_frame.pack(fill=tk.X, pady=5)
        ttk.Label(date_format_frame, text="Date folder format:").pack(side=tk.LEFT)
        self.date_format_var = tk.StringVar(value=self.config.get('date_folder_format'))
        ttk.Radiobutton(date_format_frame, text="Daily", variable=self.date_format_var, value='daily').pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(date_format_frame, text="Weekly", variable=self.date_format_var, value='weekly').pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(date_format_frame, text="Monthly", variable=self.date_format_var, value='monthly').pack(side=tk.LEFT, padx=5)
        
        max_files_frame = ttk.Frame(files_frame)
        max_files_frame.pack(fill=tk.X, pady=5)
        ttk.Label(max_files_frame, text="Max files per folder:").pack(side=tk.LEFT)
        self.max_files_var = tk.StringVar(value=str(self.config.get('max_files_per_folder')))
        ttk.Spinbox(max_files_frame, from_=0, to=1000, increment=50, textvariable=self.max_files_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(max_files_frame, text="(0 = unlimited)").pack(side=tk.LEFT)
        
        ttk.Label(files_frame, text="Filename Template", style='Header.TLabel').pack(anchor=tk.W, pady=(15, 0))
        ttk.Separator(files_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        self.template_var = tk.StringVar(value=self.config.get('filename_template'))
        ttk.Entry(files_frame, textvariable=self.template_var, width=40).pack(anchor=tk.W, pady=5)
        ttk.Label(files_frame, text="Variables: {document}, {date}, {time}, {datetime}, {year}, {month}, {day}", font=('Segoe UI', 8)).pack(anchor=tk.W)
        
        # === Filters Tab ===
        filters_frame = ttk.Frame(notebook, padding=15)
        notebook.add(filters_frame, text="Filters")
        
        ttk.Label(filters_frame, text="Document Filters", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Separator(filters_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        ttk.Label(filters_frame, text="Whitelist (only capture these, comma-separated):").pack(anchor=tk.W)
        self.whitelist_var = tk.StringVar(value=self.config.get('filename_whitelist'))
        ttk.Entry(filters_frame, textvariable=self.whitelist_var, width=50).pack(anchor=tk.W, pady=5)
        
        ttk.Label(filters_frame, text="Blacklist (never capture these, comma-separated):").pack(anchor=tk.W)
        self.blacklist_var = tk.StringVar(value=self.config.get('filename_blacklist'))
        ttk.Entry(filters_frame, textvariable=self.blacklist_var, width=50).pack(anchor=tk.W, pady=5)
        
        ttk.Label(filters_frame, text="Window Size Filters", style='Header.TLabel').pack(anchor=tk.W, pady=(15, 0))
        ttk.Separator(filters_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        min_w_frame = ttk.Frame(filters_frame)
        min_w_frame.pack(fill=tk.X, pady=5)
        ttk.Label(min_w_frame, text="Min window width:").pack(side=tk.LEFT)
        self.min_win_w_var = tk.StringVar(value=str(self.config.get('min_window_width')))
        ttk.Spinbox(min_w_frame, from_=0, to=1000, increment=50, textvariable=self.min_win_w_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(min_w_frame, text="pixels").pack(side=tk.LEFT)
        
        min_h_frame = ttk.Frame(filters_frame)
        min_h_frame.pack(fill=tk.X, pady=5)
        ttk.Label(min_h_frame, text="Min window height:").pack(side=tk.LEFT)
        self.min_win_h_var = tk.StringVar(value=str(self.config.get('min_window_height')))
        ttk.Spinbox(min_h_frame, from_=0, to=1000, increment=50, textvariable=self.min_win_h_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(min_h_frame, text="pixels").pack(side=tk.LEFT)
        
        # === Notifications Tab ===
        notif_frame = ttk.Frame(notebook, padding=15)
        notebook.add(notif_frame, text="Notifications")
        
        ttk.Label(notif_frame, text="Notification Settings", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Separator(notif_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        dur_frame = ttk.Frame(notif_frame)
        dur_frame.pack(fill=tk.X, pady=5)
        ttk.Label(dur_frame, text="Notification duration:").pack(side=tk.LEFT)
        self.notif_dur_var = tk.StringVar(value=str(self.config.get('notification_duration')))
        ttk.Spinbox(dur_frame, from_=1, to=10, increment=1, textvariable=self.notif_dur_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(dur_frame, text="seconds").pack(side=tk.LEFT)
        
        vol_frame = ttk.Frame(notif_frame)
        vol_frame.pack(fill=tk.X, pady=5)
        ttk.Label(vol_frame, text="Sound volume:").pack(side=tk.LEFT)
        self.volume_var = tk.StringVar(value=str(self.config.get('sound_volume')))
        ttk.Spinbox(vol_frame, from_=0, to=100, increment=10, textvariable=self.volume_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(vol_frame, text="%").pack(side=tk.LEFT)
        
        ttk.Label(notif_frame, text="Custom sound file (.wav):").pack(anchor=tk.W, pady=(10, 0))
        sound_frame = ttk.Frame(notif_frame)
        sound_frame.pack(fill=tk.X, pady=5)
        self.sound_file_var = tk.StringVar(value=self.config.get('custom_sound_file'))
        ttk.Entry(sound_frame, textvariable=self.sound_file_var, width=40).pack(side=tk.LEFT)
        ttk.Button(sound_frame, text="Browse", command=self.browse_sound).pack(side=tk.LEFT, padx=5)
        
        # === Updates Tab ===
        updates_frame = ttk.Frame(notebook, padding=15)
        notebook.add(updates_frame, text="Updates")
        
        ttk.Label(updates_frame, text="Auto-Update Settings", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Separator(updates_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        self.auto_update_var = tk.BooleanVar(value=self.config.get('auto_update_check'))
        ttk.Checkbutton(
            updates_frame, 
            text="Automatically check for updates",
            variable=self.auto_update_var
        ).pack(anchor=tk.W, pady=2)
        
        interval_frame = ttk.Frame(updates_frame)
        interval_frame.pack(fill=tk.X, pady=5)
        ttk.Label(interval_frame, text="Check every:").pack(side=tk.LEFT)
        self.update_interval_var = tk.StringVar(value=str(self.config.get('update_check_interval')))
        ttk.Spinbox(interval_frame, from_=1, to=168, increment=1, textvariable=self.update_interval_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(interval_frame, text="hours").pack(side=tk.LEFT)
        
        ttk.Separator(updates_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)
        
        ttk.Label(updates_frame, text="Current Version", style='Header.TLabel').pack(anchor=tk.W)
        ttk.Separator(updates_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        ttk.Label(updates_frame, text=f"Version: {APP_VERSION}", font=('Segoe UI', 10)).pack(anchor=tk.W, pady=5)
        
        skipped = self.config.get('skipped_version')
        if skipped:
            skip_frame = ttk.Frame(updates_frame)
            skip_frame.pack(fill=tk.X, pady=5)
            ttk.Label(skip_frame, text=f"Skipped version: {skipped}").pack(side=tk.LEFT)
            ttk.Button(skip_frame, text="Clear", command=self.clear_skipped_version).pack(side=tk.LEFT, padx=10)
        
        # Save/Close buttons
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(btn_frame, text="Save All", command=self.save_all).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Close", command=self.close).pack(side=tk.RIGHT)
        
        # Center window
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (325)
        y = (self.window.winfo_screenheight() // 2) - (350)
        self.window.geometry(f'+{x}+{y}')
        
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.mainloop()
    
    def browse_sound(self):
        from tkinter import filedialog
        file = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])
        if file:
            self.sound_file_var.set(file)
    
    def save_all(self):
        # Capture settings
        self.config.set('capture_on_click', self.click_var.get())
        self.config.set('capture_cooldown', float(self.cooldown_var.get()))
        self.config.set('min_scroll_distance', int(self.min_scroll_var.get()))
        self.config.set('max_captures_per_document', int(self.max_captures_var.get()))
        
        # Image settings
        self.config.set('grayscale_mode', self.grayscale_var.get())
        self.config.set('add_border', self.border_var.get())
        self.config.set('border_size', int(self.border_size_var.get()))
        self.config.set('border_color', self.border_color_var.get())
        self.config.set('max_image_width', int(self.max_width_var.get()))
        self.config.set('max_image_height', int(self.max_height_var.get()))
        
        # File settings
        self.config.set('organize_by_date', self.date_org_var.get())
        self.config.set('date_folder_format', self.date_format_var.get())
        self.config.set('max_files_per_folder', int(self.max_files_var.get()))
        self.config.set('filename_template', self.template_var.get())
        
        # Filter settings
        self.config.set('filename_whitelist', self.whitelist_var.get())
        self.config.set('filename_blacklist', self.blacklist_var.get())
        self.config.set('min_window_width', int(self.min_win_w_var.get()))
        self.config.set('min_window_height', int(self.min_win_h_var.get()))
        
        # Notification settings
        self.config.set('notification_duration', int(self.notif_dur_var.get()))
        self.config.set('sound_volume', int(self.volume_var.get()))
        self.config.set('custom_sound_file', self.sound_file_var.get())
        
        # Update settings
        self.config.set('auto_update_check', self.auto_update_var.get())
        self.config.set('update_check_interval', int(self.update_interval_var.get()))
        
        logger.info("Advanced settings saved")
        self.close()
    
    def clear_skipped_version(self):
        """Clear the skipped version."""
        self.config.set('skipped_version', None)
        logger.info("Cleared skipped version")
    
    def close(self):
        if self.window:
            self.window.destroy()
            self.window = None


class PDFScreenshotTool:
    """Main application class."""
    
    # Icon colors for different states
    COLORS = {
        'active': '#22c55e',      # Green - Acrobat active, capturing
        'enabled': '#2563eb',     # Blue - Enabled, waiting
        'disabled': '#71717a',    # Gray - Disabled
        'paused': '#f59e0b',      # Orange - Paused
    }
    
    def __init__(self):
        self.config = Config()
        self.stats = Statistics()
        self.session_manager = SessionManager(self.config)
        self.update_checker = UpdateChecker(self.config)
        self.monitor = AcrobatMonitor(
            self.config, 
            self.stats,
            self.session_manager,
            self.on_capture,
            self.on_status_change,
            self.open_folder,
            self.open_settings
        )
        self.settings_window = SettingsWindow(self.config, self.monitor, self.stats)
        self.icon = None
        self.current_status = 'enabled'
        
        # Status monitoring thread
        self.status_thread = None
        self.running = True
        
    def create_icon_image(self, color=None):
        """Create a simple icon for the system tray."""
        if color is None:
            color = self.COLORS.get(self.current_status, self.COLORS['enabled'])
        
        width = 64
        height = 64
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw a camera shape
        # Main body
        draw.rounded_rectangle([8, 20, 56, 52], radius=5, fill=color)
        # Lens - slightly darker
        draw.ellipse([22, 26, 42, 46], fill='#1e40af')
        draw.ellipse([26, 30, 38, 42], fill='#60a5fa')
        # Flash
        draw.rectangle([12, 16, 24, 22], fill=color)
        
        return image
    
    def update_icon_status(self):
        """Update the tray icon based on current status."""
        while self.running:
            try:
                is_acrobat, _, _ = self.monitor.is_acrobat_active()
                
                if self.monitor.paused:
                    new_status = 'paused'
                elif not self.config.get('enabled'):
                    new_status = 'disabled'
                elif is_acrobat:
                    new_status = 'active'
                else:
                    new_status = 'enabled'
                
                if new_status != self.current_status:
                    self.current_status = new_status
                    if self.icon:
                        self.icon.icon = self.create_icon_image()
                        
                        # Update tooltip
                        status_text = {
                            'active': 'Capturing (Acrobat active)',
                            'enabled': 'Ready (waiting for Acrobat)',
                            'disabled': 'Disabled',
                            'paused': 'Paused (Ctrl+Shift+P to resume)'
                        }
                        self.icon.title = f"PDF Screenshot Tool - {status_text.get(new_status, 'Ready')}"
            except Exception:
                pass
            
            time.sleep(1)
    
    def auto_cleanup_task(self):
        """Periodically run auto cleanup if enabled."""
        while self.running:
            try:
                if self.config.get('auto_cleanup_enabled'):
                    days = self.config.get('auto_cleanup_days')
                    folder = self.config.get('save_folder')
                    deleted = cleanup_old_screenshots(folder, days)
                    if deleted > 0:
                        logger.info(f"Auto-cleanup: deleted {deleted} old screenshots")
            except Exception as e:
                logger.error(f"Auto-cleanup error: {e}")
            
            # Run cleanup once per hour
            time.sleep(3600)
    
    def on_capture(self, filepath, doc_name):
        """Called when a screenshot is captured."""
        logger.info(f"Screenshot saved: {filepath}")
        
        # Show notification if enabled
        if self.config.get('show_notifications') and self.icon:
            try:
                self.icon.notify(
                    f"Captured: {doc_name}",
                    "PDF Screenshot Tool"
                )
            except Exception as e:
                logger.debug(f"Could not show notification: {e}")
    
    def on_status_change(self, status):
        """Called when monitoring status changes."""
        self.current_status = status
        if self.icon:
            self.icon.icon = self.create_icon_image()
    
    def open_settings(self, icon=None, item=None):
        """Open settings window in a new thread."""
        thread = threading.Thread(target=self.settings_window.show, daemon=True)
        thread.start()
    
    def toggle_enabled(self, icon, item):
        """Toggle screenshot capture on/off."""
        current = self.config.get('enabled')
        self.config.set('enabled', not current)
        logger.info(f"Capture {'enabled' if not current else 'disabled'}")
        
    def is_enabled(self, item):
        """Check if enabled for menu checkmark."""
        return self.config.get('enabled')
    
    def toggle_pause(self, icon=None, item=None):
        """Toggle pause/resume."""
        self.monitor.toggle_pause()
    
    def is_paused(self, item):
        """Check if paused for menu checkmark."""
        return self.monitor.paused
    
    def capture_now(self, icon=None, item=None):
        """Manually capture screenshot now."""
        threading.Thread(
            target=lambda: self.monitor.capture_screenshot(manual=True), 
            daemon=True
        ).start()
    
    def open_folder(self, icon=None, item=None):
        """Open the screenshot folder."""
        import subprocess
        folder = self.config.get('save_folder')
        Path(folder).mkdir(parents=True, exist_ok=True)
        subprocess.Popen(f'explorer "{folder}"')
    
    def show_recent(self, icon=None, item=None):
        """Show recent captures window."""
        recent_window = RecentCapturesWindow(self.monitor, self.config)
        threading.Thread(target=recent_window.show, daemon=True).start()
    
    def show_statistics(self, icon=None, item=None):
        """Show statistics window."""
        stats_window = StatisticsWindow(self.stats, self.config)
        threading.Thread(target=stats_window.show, daemon=True).start()
    
    def show_batch_actions(self, icon=None, item=None):
        """Show batch actions window."""
        batch_window = BatchActionsWindow(self.config)
        threading.Thread(target=batch_window.show, daemon=True).start()
    
    def start_session(self, icon=None, item=None):
        """Start a new capture session."""
        name = self.session_manager.start_session()
        if self.icon:
            try:
                self.icon.notify(f"Session started: {name}", "PDF Screenshot Tool")
            except Exception:
                pass
    
    def end_session(self, icon=None, item=None):
        """End the current capture session."""
        if self.session_manager.current_session:
            info = self.session_manager.end_session()
            if self.icon:
                try:
                    self.icon.notify(f"Session ended: {len(info['captures'])} captures", "PDF Screenshot Tool")
                except Exception:
                    pass
    
    def has_session(self, item):
        """Check if a session is active."""
        return self.session_manager.current_session is not None
    
    def check_for_updates(self, icon=None, item=None):
        """Manually check for updates."""
        def on_update_result(version, notes, url):
            if version:
                self.show_update_dialog(version, notes, url)
            else:
                # Show "no updates" notification
                if self.icon:
                    self.icon.notify(
                        "No Updates Available",
                        f"You're running the latest version (v{APP_VERSION})"
                    )
        
        self.update_checker.check_for_updates(force=True, callback=on_update_result)
    
    def auto_check_updates(self):
        """Auto-check for updates on startup."""
        def on_update_result(version, notes, url):
            if version:
                self.show_update_dialog(version, notes, url)
        
        self.update_checker.check_for_updates(force=False, callback=on_update_result)
    
    def show_update_dialog(self, version, notes, url):
        """Show update available dialog."""
        def show_dialog():
            import tkinter as tk
            from tkinter import messagebox, scrolledtext
            
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            # Create custom dialog
            dialog = tk.Toplevel(root)
            dialog.title("Update Available")
            dialog.geometry("450x350")
            dialog.resizable(False, False)
            dialog.attributes('-topmost', True)
            
            # Center on screen
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() - 450) // 2
            y = (dialog.winfo_screenheight() - 350) // 2
            dialog.geometry(f"+{x}+{y}")
            
            # Header
            header = tk.Frame(dialog, bg='#f97316', height=60)
            header.pack(fill=tk.X)
            header.pack_propagate(False)
            
            tk.Label(
                header,
                text="🎉 New Version Available!",
                font=('Segoe UI', 14, 'bold'),
                fg='white',
                bg='#f97316'
            ).pack(expand=True)
            
            # Content frame
            content = tk.Frame(dialog, padx=20, pady=15)
            content.pack(fill=tk.BOTH, expand=True)
            
            tk.Label(
                content,
                text=f"Version {version} is now available",
                font=('Segoe UI', 11),
                fg='#1a1a2e'
            ).pack(anchor=tk.W)
            
            tk.Label(
                content,
                text=f"You have version {APP_VERSION}",
                font=('Segoe UI', 9),
                fg='#666666'
            ).pack(anchor=tk.W, pady=(0, 10))
            
            # Release notes
            if notes:
                tk.Label(
                    content,
                    text="What's New:",
                    font=('Segoe UI', 10, 'bold'),
                    fg='#1a1a2e'
                ).pack(anchor=tk.W, pady=(5, 3))
                
                notes_text = scrolledtext.ScrolledText(
                    content,
                    height=8,
                    font=('Segoe UI', 9),
                    wrap=tk.WORD,
                    bg='#f5f5f5',
                    relief=tk.FLAT
                )
                notes_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
                notes_text.insert(tk.END, notes[:500] + ('...' if len(notes) > 500 else ''))
                notes_text.config(state=tk.DISABLED)
            
            # Buttons
            btn_frame = tk.Frame(dialog)
            btn_frame.pack(fill=tk.X, padx=20, pady=15)
            
            result = {'action': None}
            
            def download_update():
                result['action'] = 'download'
                dialog.destroy()
                root.destroy()
            
            def skip_version():
                result['action'] = 'skip'
                dialog.destroy()
                root.destroy()
            
            def remind_later():
                result['action'] = 'later'
                dialog.destroy()
                root.destroy()
            
            tk.Button(
                btn_frame,
                text="Download & Install",
                command=download_update,
                font=('Segoe UI', 10),
                bg='#22c55e',
                fg='white',
                relief=tk.FLAT,
                padx=15,
                pady=5,
                cursor='hand2'
            ).pack(side=tk.LEFT)
            
            tk.Button(
                btn_frame,
                text="Skip This Version",
                command=skip_version,
                font=('Segoe UI', 10),
                relief=tk.FLAT,
                padx=10,
                pady=5
            ).pack(side=tk.LEFT, padx=10)
            
            tk.Button(
                btn_frame,
                text="Remind Later",
                command=remind_later,
                font=('Segoe UI', 10),
                relief=tk.FLAT,
                padx=10,
                pady=5
            ).pack(side=tk.RIGHT)
            
            dialog.protocol("WM_DELETE_WINDOW", remind_later)
            dialog.wait_window()
            
            # Handle result
            if result['action'] == 'download':
                self.start_update_download(url)
            elif result['action'] == 'skip':
                self.update_checker.skip_version(version)
        
        # Run in main thread
        threading.Thread(target=show_dialog, daemon=True).start()
    
    def start_update_download(self, url):
        """Start downloading and installing the update."""
        def show_progress():
            import tkinter as tk
            from tkinter import ttk
            
            root = tk.Tk()
            root.title("Downloading Update")
            root.geometry("350x120")
            root.resizable(False, False)
            root.attributes('-topmost', True)
            
            # Center on screen
            root.update_idletasks()
            x = (root.winfo_screenwidth() - 350) // 2
            y = (root.winfo_screenheight() - 120) // 2
            root.geometry(f"+{x}+{y}")
            
            frame = tk.Frame(root, padx=20, pady=20)
            frame.pack(fill=tk.BOTH, expand=True)
            
            status_label = tk.Label(
                frame,
                text="Downloading update...",
                font=('Segoe UI', 10)
            )
            status_label.pack()
            
            progress = ttk.Progressbar(
                frame,
                mode='determinate',
                length=280
            )
            progress.pack(pady=15)
            
            percent_label = tk.Label(
                frame,
                text="0%",
                font=('Segoe UI', 9),
                fg='#666666'
            )
            percent_label.pack()
            
            def on_progress(status, value):
                if status == 'downloading':
                    progress['value'] = value
                    percent_label.config(text=f"{value}%")
                elif status == 'installing':
                    status_label.config(text="Starting installer...")
                    progress['value'] = 100
                    percent_label.config(text="100%")
                elif status == 'done':
                    root.destroy()
                    # Quit the app to allow installer to run
                    self.running = False
                    self.monitor.stop()
                    if self.icon:
                        self.icon.stop()
                elif status == 'error':
                    status_label.config(text=f"Error: {value}")
                    progress['value'] = 0
            
            # Start download
            self.update_checker.download_and_install(callback=lambda s, v: root.after(0, on_progress, s, v))
            
            root.mainloop()
        
        threading.Thread(target=show_progress, daemon=True).start()
    
    def quit_app(self, icon, item):
        """Quit the application."""
        logger.info("Application shutting down")
        self.running = False
        self.monitor.stop()
        icon.stop()
    
    def run(self):
        """Run the application."""
        logger.info("PDF Screenshot Tool starting...")
        
        # Show first-run setup if this is the first launch
        if self.config.is_first_run:
            logger.info("First run detected, showing setup wizard")
            setup = FirstRunSetup(self.config)
            setup.show()
        
        # Start the monitor
        self.monitor.start()
        
        # Start status monitoring thread
        self.status_thread = threading.Thread(target=self.update_icon_status, daemon=True)
        self.status_thread.start()
        
        # Start auto-cleanup thread
        cleanup_thread = threading.Thread(target=self.auto_cleanup_task, daemon=True)
        cleanup_thread.start()
        
        # Create system tray icon with expanded menu
        menu = pystray.Menu(
            pystray.MenuItem(
                "Enabled",
                self.toggle_enabled,
                checked=self.is_enabled
            ),
            pystray.MenuItem(
                "Paused",
                self.toggle_pause,
                checked=self.is_paused
            ),
            pystray.MenuItem("Capture Now (Ctrl+Shift+S)", self.capture_now),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Session",
                pystray.Menu(
                    pystray.MenuItem("Start New Session", self.start_session),
                    pystray.MenuItem("End Session", self.end_session, enabled=self.has_session),
                )
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Recent Captures", self.show_recent),
            pystray.MenuItem("Statistics", self.show_statistics),
            pystray.MenuItem("Batch Actions", self.show_batch_actions),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Screenshot Folder", self.open_folder),
            pystray.MenuItem("Settings...", self.open_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(f"Check for Updates (v{APP_VERSION})", self.check_for_updates),
            pystray.MenuItem("Quit", self.quit_app)
        )
        
        self.icon = pystray.Icon(
            "PDF Screenshot Tool",
            self.create_icon_image(),
            "PDF Screenshot Tool - Ready",
            menu
        )
        
        logger.info("PDF Screenshot Tool is running")
        
        # Check for updates on startup (if enabled)
        if self.config.get('auto_update_check'):
            threading.Timer(5.0, self.auto_check_updates).start()
        
        self.icon.run()


def main():
    app = PDFScreenshotTool()
    app.run()


if __name__ == '__main__':
    main()
