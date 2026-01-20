"""
Generate icon.ico for PDF Screenshot Tool
Run this script once to create the application icon.
"""

from PIL import Image, ImageDraw
import os

def create_icon():
    """Create a professional camera icon for the application."""
    
    # Create assets directory if it doesn't exist
    assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
    os.makedirs(assets_dir, exist_ok=True)
    
    # Icon sizes for Windows ICO format
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = []
    
    for size in sizes:
        # Create image with transparent background
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Scale factor
        s = size / 64
        
        # Colors
        primary = '#2563eb'      # Blue
        primary_dark = '#1e40af' # Dark blue
        primary_light = '#60a5fa' # Light blue
        white = '#ffffff'
        
        # Draw camera body (rounded rectangle)
        body_left = int(8 * s)
        body_top = int(20 * s)
        body_right = int(56 * s)
        body_bottom = int(52 * s)
        
        # Camera body
        draw.rounded_rectangle(
            [body_left, body_top, body_right, body_bottom],
            radius=int(5 * s),
            fill=primary
        )
        
        # Camera flash/viewfinder bump
        flash_left = int(12 * s)
        flash_top = int(14 * s)
        flash_right = int(26 * s)
        flash_bottom = int(22 * s)
        draw.rectangle([flash_left, flash_top, flash_right, flash_bottom], fill=primary)
        
        # Lens outer circle
        lens_center = (int(32 * s), int(36 * s))
        lens_outer_radius = int(10 * s)
        lens_inner_radius = int(6 * s)
        
        draw.ellipse(
            [lens_center[0] - lens_outer_radius, lens_center[1] - lens_outer_radius,
             lens_center[0] + lens_outer_radius, lens_center[1] + lens_outer_radius],
            fill=primary_dark
        )
        
        # Lens inner circle (highlight)
        draw.ellipse(
            [lens_center[0] - lens_inner_radius, lens_center[1] - lens_inner_radius,
             lens_center[0] + lens_inner_radius, lens_center[1] + lens_inner_radius],
            fill=primary_light
        )
        
        # Small lens reflection
        if size >= 32:
            reflection_size = max(2, int(2 * s))
            reflection_x = lens_center[0] - int(3 * s)
            reflection_y = lens_center[1] - int(3 * s)
            draw.ellipse(
                [reflection_x, reflection_y, 
                 reflection_x + reflection_size, reflection_y + reflection_size],
                fill=white
            )
        
        # Shutter button
        if size >= 24:
            shutter_left = int(42 * s)
            shutter_top = int(16 * s)
            shutter_right = int(50 * s)
            shutter_bottom = int(20 * s)
            draw.rounded_rectangle(
                [shutter_left, shutter_top, shutter_right, shutter_bottom],
                radius=int(2 * s),
                fill=primary_dark
            )
        
        images.append(img)
    
    # Save as ICO file
    icon_path = os.path.join(assets_dir, 'icon.ico')
    
    # Save with multiple sizes
    images[0].save(
        icon_path,
        format='ICO',
        sizes=[(img.width, img.height) for img in images],
        append_images=images[1:]
    )
    
    print(f"Icon created successfully: {icon_path}")
    return icon_path


if __name__ == '__main__':
    create_icon()

