"""
Create custom images for the Inno Setup installer.
More visually interesting with gradients, patterns, and branding.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math
import os

def create_gradient(draw, width, height, color1, color2, direction='vertical'):
    """Create a gradient between two colors."""
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    
    for i in range(height if direction == 'vertical' else width):
        ratio = i / (height if direction == 'vertical' else width)
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        
        if direction == 'vertical':
            draw.line([(0, i), (width, i)], fill=(r, g, b))
        else:
            draw.line([(i, 0), (i, height)], fill=(r, g, b))


def draw_camera_icon(draw, x, y, size, color_body, color_lens_outer, color_lens_inner):
    """Draw a stylized camera icon."""
    # Body proportions
    body_w = size
    body_h = int(size * 0.7)
    
    # Camera body with rounded corners
    draw.rounded_rectangle(
        [x, y, x + body_w, y + body_h],
        radius=int(size * 0.15),
        fill=color_body
    )
    
    # Flash/viewfinder bump
    bump_w = int(size * 0.3)
    bump_h = int(size * 0.15)
    draw.rounded_rectangle(
        [x + int(size * 0.1), y - bump_h + 2, x + int(size * 0.1) + bump_w, y + 4],
        radius=3,
        fill=color_body
    )
    
    # Lens - outer ring
    lens_cx = x + body_w // 2
    lens_cy = y + body_h // 2
    lens_r = int(size * 0.28)
    
    # Outer lens ring
    draw.ellipse(
        [lens_cx - lens_r, lens_cy - lens_r, lens_cx + lens_r, lens_cy + lens_r],
        fill=color_lens_outer
    )
    
    # Inner lens
    inner_r = int(lens_r * 0.7)
    draw.ellipse(
        [lens_cx - inner_r, lens_cy - inner_r, lens_cx + inner_r, lens_cy + inner_r],
        fill=color_lens_inner
    )
    
    # Lens highlight
    highlight_r = int(inner_r * 0.3)
    highlight_offset = int(inner_r * 0.2)
    draw.ellipse(
        [lens_cx - highlight_offset - highlight_r, lens_cy - highlight_offset - highlight_r,
         lens_cx - highlight_offset + highlight_r, lens_cy - highlight_offset + highlight_r],
        fill='white'
    )


def draw_decorative_circles(draw, width, height, color, count=8):
    """Draw decorative floating circles."""
    import random
    random.seed(42)  # Consistent placement
    
    for _ in range(count):
        x = random.randint(0, width)
        y = random.randint(0, height)
        r = random.randint(5, 25)
        opacity = random.randint(30, 80)
        
        # Draw circle outline
        draw.ellipse(
            [x - r, y - r, x + r, y + r],
            outline=color,
            width=2
        )


def draw_pdf_pages(draw, x, y, size):
    """Draw stacked PDF page icons."""
    page_w = int(size * 0.6)
    page_h = int(size * 0.8)
    offset = 6
    
    # Back pages (lighter)
    for i in range(2, -1, -1):
        px = x + i * offset
        py = y + i * offset
        
        # Page shadow
        draw.rounded_rectangle(
            [px + 2, py + 2, px + page_w + 2, py + page_h + 2],
            radius=3,
            fill=(30, 30, 50)
        )
        
        # Page
        color = (240 - i * 20, 240 - i * 20, 240 - i * 15)
        draw.rounded_rectangle(
            [px, py, px + page_w, py + page_h],
            radius=3,
            fill=color
        )
        
        # Page corner fold
        fold_size = int(page_w * 0.2)
        if i == 0:
            draw.polygon([
                (px + page_w - fold_size, py),
                (px + page_w, py),
                (px + page_w, py + fold_size)
            ], fill=(220, 220, 215))
            
            # Lines on front page
            for line_y in range(py + 12, py + page_h - 10, 8):
                line_len = random.randint(page_w - 20, page_w - 8)
                draw.line([(px + 6, line_y), (px + 6 + line_len, line_y)], fill=(200, 200, 200), width=2)


import random

def create_wizard_image():
    """Create the large wizard image (164x314 for modern style)."""
    width, height = 164, 314
    
    img = Image.new('RGB', (width, height), '#1a1a2e')
    draw = ImageDraw.Draw(img)
    
    # Rich gradient background: deep purple to vibrant orange
    create_gradient(draw, width, height, (26, 26, 46), (40, 20, 60), 'vertical')
    
    # Add diagonal gradient overlay
    for y in range(height):
        for x in range(width):
            ratio = (x + y) / (width + height)
            current = img.getpixel((x, y))
            
            # Add orange tint towards bottom-right
            r = min(255, int(current[0] + ratio * 80))
            g = min(255, int(current[1] + ratio * 30))
            b = max(0, int(current[2] - ratio * 20))
            
            img.putpixel((x, y), (r, g, b))
    
    draw = ImageDraw.Draw(img)
    
    # Decorative geometric patterns
    # Large circle outline (top)
    draw.ellipse([-30, -30, 70, 70], outline='#4f46e5', width=2)
    draw.ellipse([-20, -20, 60, 60], outline='#6366f1', width=1)
    
    # Floating circles
    draw.ellipse([120, 40, 160, 80], outline='#f97316', width=2)
    draw.ellipse([10, 220, 40, 250], outline='#22c55e', width=2)
    draw.ellipse([130, 260, 155, 285], outline='#f97316', width=1)
    
    # Main camera icon
    draw_camera_icon(draw, 45, 85, 74, '#f97316', '#1e40af', '#60a5fa')
    
    # PDF pages stack below camera
    draw_pdf_pages(draw, 55, 175, 55)
    
    # App name text
    try:
        font_large = ImageFont.truetype("segoeuib.ttf", 16)
        font_small = ImageFont.truetype("segoeui.ttf", 11)
        font_tiny = ImageFont.truetype("segoeui.ttf", 9)
    except:
        try:
            font_large = ImageFont.truetype("arial.ttf", 16)
            font_small = ImageFont.truetype("arial.ttf", 11)
            font_tiny = ImageFont.truetype("arial.ttf", 9)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
            font_tiny = ImageFont.load_default()
    
    # Brand text
    draw.text((32, 252), "PDF Screenshot", fill='white', font=font_large)
    draw.text((60, 272), "Tool", fill='#a8a29e', font=font_large)
    
    # Version badge
    draw.rounded_rectangle([55, 292, 110, 308], radius=8, fill='#f97316')
    draw.text((66, 294), "v2.0.0", fill='white', font=font_tiny)
    
    # Subtle grid pattern
    for i in range(0, width, 20):
        draw.line([(i, 0), (i, height)], fill=(255, 255, 255, 5), width=1)
    for i in range(0, height, 20):
        draw.line([(0, i), (width, i)], fill=(255, 255, 255, 5), width=1)
    
    img.save('assets/wizard_image.bmp', 'BMP')
    print("Created wizard_image.bmp (164x314)")


def create_wizard_small_image():
    """Create the small wizard image (55x55 for modern style header)."""
    width, height = 55, 55
    
    img = Image.new('RGB', (width, height), '#1a1a2e')
    draw = ImageDraw.Draw(img)
    
    # Gradient background
    create_gradient(draw, width, height, (26, 26, 46), (50, 30, 60), 'vertical')
    
    # Add subtle orange tint
    for y in range(height):
        for x in range(width):
            ratio = (x + y) / (width + height)
            current = img.getpixel((x, y))
            r = min(255, int(current[0] + ratio * 40))
            img.putpixel((x, y), (r, current[1], current[2]))
    
    draw = ImageDraw.Draw(img)
    
    # Camera icon
    draw_camera_icon(draw, 7, 12, 40, '#f97316', '#1e40af', '#60a5fa')
    
    # Corner accent
    draw.polygon([(0, 0), (15, 0), (0, 15)], fill='#4f46e5')
    
    img.save('assets/wizard_small_image.bmp', 'BMP')
    print("Created wizard_small_image.bmp (55x55)")


if __name__ == '__main__':
    os.makedirs('assets', exist_ok=True)
    create_wizard_image()
    create_wizard_small_image()
    print("\nDone! Installer images created in assets/ folder.")
