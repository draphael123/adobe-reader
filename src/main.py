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
from datetime import datetime
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
    
    def __init__(self, config, on_capture_callback=None, on_status_change=None):
        self.config = config
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
        
        # Manual hotkey tracking
        self.current_keys = set()
        self.hotkey_keys = {keyboard.Key.ctrl_l, keyboard.Key.shift, keyboard.KeyCode.from_char('s')}
        
    def is_acrobat_active(self):
        """Check if Adobe Acrobat is the active window."""
        try:
            active_window = gw.getActiveWindow()
            if active_window:
                title = active_window.title
                for acrobat_title in self.ACROBAT_TITLES:
                    if acrobat_title in title:
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
    
    def capture_screenshot(self, manual=False):
        """Capture screenshot of the Acrobat window."""
        with self.capture_lock:
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
                # Get window position and size, handling negative coordinates
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
                    
                    # Organize by document if enabled
                    if self.config.get('organize_by_document'):
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
    
    def check_hotkey(self):
        """Check if manual capture hotkey is pressed."""
        # Check for Ctrl+Shift+S
        ctrl_pressed = keyboard.Key.ctrl_l in self.current_keys or keyboard.Key.ctrl_r in self.current_keys
        shift_pressed = keyboard.Key.shift in self.current_keys or keyboard.Key.shift_r in self.current_keys
        s_pressed = keyboard.KeyCode.from_char('s') in self.current_keys
        
        return ctrl_pressed and shift_pressed and s_pressed
    
    def on_key_press(self, key):
        """Handle key press events (non-blocking)."""
        # Track current keys for hotkey detection
        self.current_keys.add(key)
        
        # Check for manual capture hotkey (Ctrl+Shift+S)
        if self.config.get('hotkey_enabled') and self.check_hotkey():
            logger.info("Manual capture hotkey triggered")
            threading.Thread(target=lambda: self.capture_screenshot(manual=True), daemon=True).start()
            return
        
        if not self.config.get('enabled'):
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
        if not self.config.get('enabled'):
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
        self.window.geometry("550x500")
        self.window.resizable(False, False)
        
        # Try to set window icon
        try:
            icon_path = Path(__file__).parent.parent / 'assets' / 'icon.ico'
            if icon_path.exists():
                self.window.iconbitmap(str(icon_path))
        except Exception:
            pass
        
        # Style
        style = ttk.Style()
        style.configure('Title.TLabel', font=('Segoe UI', 18, 'bold'))
        style.configure('Subtitle.TLabel', font=('Segoe UI', 11))
        style.configure('Header.TLabel', font=('Segoe UI', 10, 'bold'))
        
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
        
        info_text = """1. The app runs in the system tray (bottom-right, near the clock)
2. Open any PDF in Adobe Acrobat or Adobe Reader
3. Navigate pages using Page Up/Down, arrow keys, or scroll
4. Screenshots are captured automatically!

💡 Tip: Press Ctrl+Shift+S to capture manually anytime."""
        
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor=tk.W)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        
        start_btn = ttk.Button(
            btn_frame, 
            text="Start Using PDF Screenshot Tool →", 
            command=self.finish_setup
        )
        start_btn.pack(side=tk.RIGHT)
        
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
        self.config.set('show_notifications', self.notify_var.get())
        
        # Handle startup setting
        if self.startup_var.get():
            set_startup_registry(True)
        self.config.set('start_with_windows', self.startup_var.get())
        
        self.completed = True
        self.window.destroy()
        logger.info("First-run setup completed")


class SettingsWindow:
    """Settings window using tkinter."""
    
    def __init__(self, config, monitor):
        self.config = config
        self.monitor = monitor
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
        self.window.geometry("550x580")
        self.window.resizable(False, False)
        
        # Try to set window icon
        try:
            icon_path = Path(__file__).parent.parent / 'assets' / 'icon.ico'
            if icon_path.exists():
                self.window.iconbitmap(str(icon_path))
        except Exception:
            pass
        
        # Style
        style = ttk.Style()
        style.configure('TLabel', padding=5)
        style.configure('TButton', padding=5)
        style.configure('TCheckbutton', padding=5)
        style.configure('Header.TLabel', font=('Segoe UI', 10, 'bold'))
        
        # Main frame with scrollable canvas
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="PDF Screenshot Tool", font=('Segoe UI', 16, 'bold'))
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
        
        # Show notifications
        self.notify_var = tk.BooleanVar(value=self.config.get('show_notifications'))
        notify_check = ttk.Checkbutton(
            main_frame, 
            text="Show notification on capture",
            variable=self.notify_var
        )
        notify_check.pack(anchor=tk.W, pady=2)
        
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
        
        # Status
        self.status_label = ttk.Label(
            main_frame, 
            text=f"Screenshots captured this session: {self.monitor.screenshot_count}",
            font=('Segoe UI', 10)
        )
        self.status_label.pack(pady=15)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        save_btn = ttk.Button(btn_frame, text="Save Settings", command=self.save_settings)
        save_btn.pack(side=tk.LEFT)
        
        open_folder_btn = ttk.Button(btn_frame, text="Open Folder", command=self.open_folder)
        open_folder_btn.pack(side=tk.LEFT, padx=10)
        
        open_log_btn = ttk.Button(btn_frame, text="View Log", command=self.open_log)
        open_log_btn.pack(side=tk.LEFT)
        
        close_btn = ttk.Button(btn_frame, text="Close", command=self.close)
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
        self.config.set('organize_by_document', self.organize_var.get())
        self.config.set('image_format', self.format_var.get())
        self.config.set('jpeg_quality', int(self.quality_var.get()))
        
        # Handle startup setting
        set_startup_registry(self.startup_var.get())
        self.config.set('start_with_windows', self.startup_var.get())
        
        # Update status
        self.status_label.config(text="✓ Settings saved!")
        self.window.after(2000, lambda: self.status_label.config(
            text=f"Screenshots captured this session: {self.monitor.screenshot_count}"
        ))
    
    def open_folder(self):
        import subprocess
        folder = self.config.get('save_folder')
        Path(folder).mkdir(parents=True, exist_ok=True)
        subprocess.Popen(f'explorer "{folder}"')
    
    def open_log(self):
        import subprocess
        subprocess.Popen(f'notepad "{LOG_FILE}"')
    
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
    }
    
    def __init__(self):
        self.config = Config()
        self.monitor = AcrobatMonitor(
            self.config, 
            self.on_capture,
            self.on_status_change
        )
        self.settings_window = SettingsWindow(self.config, self.monitor)
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
                
                if not self.config.get('enabled'):
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
                            'disabled': 'Disabled'
                        }
                        self.icon.title = f"PDF Screenshot Tool - {status_text.get(new_status, 'Ready')}"
            except Exception:
                pass
            
            time.sleep(1)
    
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
        
        # Create system tray icon
        menu = pystray.Menu(
            pystray.MenuItem(
                "Enabled",
                self.toggle_enabled,
                checked=self.is_enabled
            ),
            pystray.MenuItem("Capture Now (Ctrl+Shift+S)", self.capture_now),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings...", self.open_settings),
            pystray.MenuItem("Open Screenshot Folder", self.open_folder),
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
