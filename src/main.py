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
    'save_folder': str(Path.home() / 'Documents' / 'PDF Screenshots'),
    'enabled': True,
    'capture_delay': 0.3,  # seconds to wait after navigation
    'hotkey_enabled': True,
    'start_with_windows': False,
    'capture_on_scroll': True,
    'image_format': 'png',  # 'png' or 'jpeg'
    'jpeg_quality': 90,
    'organize_by_document': True,  # Create subfolders per document
    'show_notifications': True,
    'manual_hotkey': 'ctrl+shift+s',
    'pause_hotkey': 'ctrl+shift+p',
    'sound_enabled': True,  # Play sound on capture
    'dark_mode': True,  # Dark mode UI
    'auto_cleanup_enabled': False,
    'auto_cleanup_days': 30,  # Delete screenshots older than X days
    'capture_document_only': False,  # Try to capture just the document area
    'portable_mode': PORTABLE_FLAG.exists(),
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


def play_capture_sound():
    """Play a camera shutter sound."""
    try:
        # Use Windows system sound
        winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        pass


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
    
    def __init__(self, config, stats, session_manager, on_capture_callback=None, on_status_change=None):
        self.config = config
        self.stats = stats
        self.session_manager = session_manager
        self.on_capture_callback = on_capture_callback
        self.on_status_change = on_status_change
        self.keyboard_listener = None
        self.mouse_listener = None
        self.last_capture_time = 0
        self.capture_cooldown = 0.5  # Minimum time between captures
        self.last_window_title = ""
        self.screenshot_count = 0
        self.last_screenshot_hash = None  # For duplicate detection
        self.pending_capture = None  # Track pending capture timer
        self.capture_lock = threading.Lock()  # Thread safety
        self.recent_captures = []  # Store recent capture paths
        self.paused = False  # Pause/resume state
        
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
                
                # Check if an actual PDF is open (title should contain .pdf)
                # Adobe shows: "Document.pdf - Adobe Acrobat Reader"
                has_pdf = '.pdf' in title.lower()
                if not has_pdf:
                    # Also check for common patterns without .pdf extension shown
                    # When a PDF is open, title won't be just "Adobe Acrobat Reader"
                    just_app_names = ['Adobe Acrobat Reader', 'Adobe Acrobat', 'Adobe Acrobat Reader DC', 'Adobe Acrobat DC']
                    if title.strip() in just_app_names:
                        return False, "", None
                
                        return True, title, active_window
        except Exception:
            pass
        return False, "", None
    
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
            
            current_time = time.time()
            if not manual and current_time - self.last_capture_time < self.capture_cooldown:
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
                    
                    # Determine save location
                    base_folder = Path(self.config.get('save_folder'))
                    doc_name = self.get_document_name(window_title)
                    
                    # Check for session folder
                    session_folder = self.session_manager.get_session_folder()
                    if session_folder:
                        save_folder = session_folder / doc_name
                    elif self.config.get('organize_by_document'):
                        save_folder = base_folder / doc_name
                    else:
                        save_folder = base_folder
                    
                    save_folder.mkdir(parents=True, exist_ok=True)
                    
                    # Generate filename with timestamp
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                    self.screenshot_count += 1
                    
                    # Determine format and save
                    img_format = self.config.get('image_format')
                    
                    if img_format == 'jpeg':
                        filename = f"{doc_name}_{timestamp}.jpg"
                        filepath = save_folder / filename
                        # Convert to PIL Image and save as JPEG
                        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                        img.save(str(filepath), "JPEG", quality=self.config.get('jpeg_quality'))
                    else:
                        filename = f"{doc_name}_{timestamp}.png"
                        filepath = save_folder / filename
                        mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(filepath))
                    
                    logger.info(f"Screenshot saved: {filepath}")
                    
                    # Play sound if enabled
                    if self.config.get('sound_enabled'):
                        play_capture_sound()
                    
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
        
        self.schedule_capture()
    
    def start(self):
        """Start monitoring keyboard and mouse."""
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_key_press,
            on_release=self.on_key_release
        )
        self.keyboard_listener.start()
        
        # Also monitor mouse scroll for PDF navigation
        self.mouse_listener = mouse.Listener(on_scroll=self.on_scroll)
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
        jpeg_radio.pack(side=tk.LEFT)
        
        # JPEG quality
        quality_frame = ttk.Frame(main_frame)
        quality_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(quality_frame, text="JPEG quality:").pack(side=tk.LEFT)
        
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
        self.monitor = AcrobatMonitor(
            self.config, 
            self.stats,
            self.session_manager,
            self.on_capture,
            self.on_status_change
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
            pystray.MenuItem("Quit", self.quit_app)
        )
        
        self.icon = pystray.Icon(
            "PDF Screenshot Tool",
            self.create_icon_image(),
            "PDF Screenshot Tool - Ready",
            menu
        )
        
        logger.info("PDF Screenshot Tool is running")
        
        self.icon.run()


def main():
    app = PDFScreenshotTool()
    app.run()


if __name__ == '__main__':
    main()
