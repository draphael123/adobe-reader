"""
PDF Screenshot Tool
Automatically captures screenshots of Adobe Acrobat pages during navigation.
"""

import sys
import os
import threading
import time
from datetime import datetime
from pathlib import Path

import pystray
from PIL import Image, ImageDraw
from pynput import keyboard
import pygetwindow as gw
import mss
import mss.tools
import json

# Configuration file path
CONFIG_DIR = Path(os.environ.get('APPDATA', Path.home())) / 'PDFScreenshotTool'
CONFIG_FILE = CONFIG_DIR / 'config.json'

# Default configuration
DEFAULT_CONFIG = {
    'save_folder': str(Path.home() / 'Documents' / 'PDF Screenshots'),
    'enabled': True,
    'capture_delay': 0.3,  # seconds to wait after navigation
    'hotkey_enabled': True,
}

class Config:
    """Manages application configuration."""
    
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load()
    
    def load(self):
        """Load configuration from file."""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
        except Exception as e:
            print(f"Error loading config: {e}")
    
    def save(self):
        """Save configuration to file."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, key):
        return self.config.get(key, DEFAULT_CONFIG.get(key))
    
    def set(self, key, value):
        self.config[key] = value
        self.save()


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
    
    def __init__(self, config, on_capture_callback=None):
        self.config = config
        self.on_capture_callback = on_capture_callback
        self.listener = None
        self.last_capture_time = 0
        self.capture_cooldown = 0.5  # Minimum time between captures
        self.last_window_title = ""
        self.screenshot_count = 0
        
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
                return window_title.split(separator)[0].strip()
        return "Unknown Document"
    
    def capture_screenshot(self):
        """Capture screenshot of the Acrobat window."""
        is_active, window_title, window = self.is_acrobat_active()
        
        if not is_active or not window:
            return None
        
        current_time = time.time()
        if current_time - self.last_capture_time < self.capture_cooldown:
            return None
        
        self.last_capture_time = current_time
        
        try:
            # Get window position and size
            left = window.left
            top = window.top
            width = window.width
            height = window.height
            
            # Capture the window region
            with mss.mss() as sct:
                monitor = {
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height
                }
                screenshot = sct.grab(monitor)
                
                # Create save folder if it doesn't exist
                save_folder = Path(self.config.get('save_folder'))
                save_folder.mkdir(parents=True, exist_ok=True)
                
                # Generate filename
                doc_name = self.get_document_name(window_title)
                # Clean document name for filesystem
                doc_name = "".join(c for c in doc_name if c.isalnum() or c in (' ', '-', '_', '.')).strip()
                doc_name = doc_name[:50]  # Limit length
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                self.screenshot_count += 1
                
                filename = f"{doc_name}_{timestamp}.png"
                filepath = save_folder / filename
                
                # Save screenshot
                mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(filepath))
                
                if self.on_capture_callback:
                    self.on_capture_callback(str(filepath))
                
                return str(filepath)
                
        except Exception as e:
            print(f"Error capturing screenshot: {e}")
            return None
    
    def on_key_press(self, key):
        """Handle key press events."""
        if not self.config.get('enabled'):
            return
        
        is_active, _, _ = self.is_acrobat_active()
        if not is_active:
            return
        
        # Check if it's a navigation key
        if key in self.NAVIGATION_KEYS:
            # Wait a moment for the page to render
            time.sleep(self.config.get('capture_delay'))
            self.capture_screenshot()
    
    def start(self):
        """Start monitoring keyboard."""
        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()
    
    def stop(self):
        """Stop monitoring."""
        if self.listener:
            self.listener.stop()


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
        self.window.geometry("500x350")
        self.window.resizable(False, False)
        
        # Style
        style = ttk.Style()
        style.configure('TLabel', padding=5)
        style.configure('TButton', padding=5)
        style.configure('TCheckbutton', padding=5)
        
        # Main frame
        main_frame = ttk.Frame(self.window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="PDF Screenshot Tool", font=('Segoe UI', 16, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Enable/Disable
        self.enabled_var = tk.BooleanVar(value=self.config.get('enabled'))
        enabled_check = ttk.Checkbutton(
            main_frame, 
            text="Enable automatic screenshots",
            variable=self.enabled_var,
            command=self.toggle_enabled
        )
        enabled_check.pack(anchor=tk.W, pady=5)
        
        # Save folder
        folder_frame = ttk.Frame(main_frame)
        folder_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(folder_frame, text="Save folder:").pack(anchor=tk.W)
        
        folder_input_frame = ttk.Frame(folder_frame)
        folder_input_frame.pack(fill=tk.X, pady=5)
        
        self.folder_var = tk.StringVar(value=self.config.get('save_folder'))
        folder_entry = ttk.Entry(folder_input_frame, textvariable=self.folder_var, width=50)
        folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        browse_btn = ttk.Button(folder_input_frame, text="Browse...", command=self.browse_folder)
        browse_btn.pack(side=tk.LEFT, padx=(10, 0))
        
        # Capture delay
        delay_frame = ttk.Frame(main_frame)
        delay_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(delay_frame, text="Capture delay (seconds):").pack(side=tk.LEFT)
        
        self.delay_var = tk.StringVar(value=str(self.config.get('capture_delay')))
        delay_spin = ttk.Spinbox(
            delay_frame, 
            from_=0.1, 
            to=2.0, 
            increment=0.1,
            textvariable=self.delay_var,
            width=10
        )
        delay_spin.pack(side=tk.LEFT, padx=(10, 0))
        
        # Status
        self.status_label = ttk.Label(main_frame, text=f"Screenshots captured this session: {self.monitor.screenshot_count}")
        self.status_label.pack(pady=20)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        save_btn = ttk.Button(btn_frame, text="Save Settings", command=self.save_settings)
        save_btn.pack(side=tk.LEFT)
        
        open_folder_btn = ttk.Button(btn_frame, text="Open Screenshot Folder", command=self.open_folder)
        open_folder_btn.pack(side=tk.LEFT, padx=10)
        
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
        
        # Update status
        self.status_label.config(text="Settings saved!")
        self.window.after(2000, lambda: self.status_label.config(
            text=f"Screenshots captured this session: {self.monitor.screenshot_count}"
        ))
    
    def open_folder(self):
        import subprocess
        folder = self.config.get('save_folder')
        Path(folder).mkdir(parents=True, exist_ok=True)
        subprocess.Popen(f'explorer "{folder}"')
    
    def close(self):
        if self.window:
            self.window.destroy()
            self.window = None


class PDFScreenshotTool:
    """Main application class."""
    
    def __init__(self):
        self.config = Config()
        self.monitor = AcrobatMonitor(self.config, self.on_capture)
        self.settings_window = SettingsWindow(self.config, self.monitor)
        self.icon = None
        
    def create_icon_image(self):
        """Create a simple icon for the system tray."""
        # Create a simple camera icon
        width = 64
        height = 64
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw a camera shape
        # Main body
        draw.rounded_rectangle([8, 20, 56, 52], radius=5, fill='#2563eb')
        # Lens
        draw.ellipse([22, 26, 42, 46], fill='#1e40af')
        draw.ellipse([26, 30, 38, 42], fill='#60a5fa')
        # Flash
        draw.rectangle([12, 16, 24, 22], fill='#2563eb')
        
        return image
    
    def on_capture(self, filepath):
        """Called when a screenshot is captured."""
        print(f"Screenshot saved: {filepath}")
    
    def open_settings(self, icon=None, item=None):
        """Open settings window in a new thread."""
        thread = threading.Thread(target=self.settings_window.show, daemon=True)
        thread.start()
    
    def toggle_enabled(self, icon, item):
        """Toggle screenshot capture on/off."""
        current = self.config.get('enabled')
        self.config.set('enabled', not current)
        
    def is_enabled(self, item):
        """Check if enabled for menu checkmark."""
        return self.config.get('enabled')
    
    def open_folder(self, icon=None, item=None):
        """Open the screenshot folder."""
        import subprocess
        folder = self.config.get('save_folder')
        Path(folder).mkdir(parents=True, exist_ok=True)
        subprocess.Popen(f'explorer "{folder}"')
    
    def quit_app(self, icon, item):
        """Quit the application."""
        self.monitor.stop()
        icon.stop()
    
    def run(self):
        """Run the application."""
        # Start the monitor
        self.monitor.start()
        
        # Create system tray icon
        menu = pystray.Menu(
            pystray.MenuItem(
                "Enabled",
                self.toggle_enabled,
                checked=self.is_enabled
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings...", self.open_settings),
            pystray.MenuItem("Open Screenshot Folder", self.open_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.quit_app)
        )
        
        self.icon = pystray.Icon(
            "PDF Screenshot Tool",
            self.create_icon_image(),
            "PDF Screenshot Tool",
            menu
        )
        
        print("PDF Screenshot Tool is running...")
        print("Right-click the system tray icon to access settings.")
        
        self.icon.run()


def main():
    app = PDFScreenshotTool()
    app.run()


if __name__ == '__main__':
    main()
