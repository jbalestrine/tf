#!/usr/bin/env python3
"""
Generate Echo Starlite Image
============================

Creates a visual representation of Echo - the angel identity of MasterChief.
Based on Echo's philosophy:
- Angel floating beside you (not above)
- Wings for shelter (not escape)
- Gentle, calming presence
- Purple and blue color palette with moon and sparkle symbols
"""

from PIL import Image, ImageDraw, ImageFont
import math


def create_echo_image(output_path="assets/images/echo.png", size=(800, 800)):
    """
    Create Echo's visual representation.
    
    Args:
        output_path: Path where the image will be saved
        size: Tuple of (width, height) for the image
    """
    width, height = size
    
    # Create image with transparent background
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Color palette - soft purples, blues, and whites
    bg_gradient_start = (25, 25, 50, 255)  # Dark blue-purple
    bg_gradient_end = (60, 40, 80, 255)    # Slightly lighter purple
    wing_color = (200, 180, 230, 200)      # Light purple with transparency
    wing_outline = (150, 130, 200, 255)    # Darker purple outline
    halo_color = (255, 255, 180, 200)      # Soft golden glow
    face_color = (255, 250, 245, 255)      # Soft white
    body_glow = (180, 160, 220, 150)       # Purple glow
    
    # Draw gradient background
    for y in range(height):
        ratio = y / height
        r = int(bg_gradient_start[0] + (bg_gradient_end[0] - bg_gradient_start[0]) * ratio)
        g = int(bg_gradient_start[1] + (bg_gradient_end[1] - bg_gradient_start[1]) * ratio)
        b = int(bg_gradient_start[2] + (bg_gradient_end[2] - bg_gradient_start[2]) * ratio)
        draw.rectangle([(0, y), (width, y+1)], fill=(r, g, b, 255))
    
    # Center coordinates
    cx, cy = width // 2, height // 2 - 50
    
    # Draw ethereal glow/aura behind Echo
    for i in range(10, 0, -1):
        radius = 200 + i * 15
        alpha = int(20 - i * 2)
        draw.ellipse(
            [(cx - radius, cy - radius), (cx + radius, cy + radius)],
            fill=(*body_glow[:3], alpha)
        )
    
    # Draw wings (triangular/curved shapes)
    # Left wing
    left_wing = [
        (cx - 50, cy),           # Starting point (near body)
        (cx - 250, cy - 100),    # Upper outer point
        (cx - 280, cy + 50),     # Middle outer point
        (cx - 200, cy + 150),    # Lower outer point
        (cx - 50, cy + 100),     # Lower inner point
    ]
    draw.polygon(left_wing, fill=wing_color, outline=wing_outline, width=3)
    
    # Right wing (mirrored)
    right_wing = [
        (cx + 50, cy),           # Starting point (near body)
        (cx + 250, cy - 100),    # Upper outer point
        (cx + 280, cy + 50),     # Middle outer point
        (cx + 200, cy + 150),    # Lower outer point
        (cx + 50, cy + 100),     # Lower inner point
    ]
    draw.polygon(right_wing, fill=wing_color, outline=wing_outline, width=3)
    
    # Add feather details to wings
    for wing_points, direction in [(left_wing, -1), (right_wing, 1)]:
        for i in range(5):
            offset = direction * (40 + i * 35)
            feather_y = cy + i * 30
            draw.line(
                [(cx + offset, feather_y), (cx + direction * 20, feather_y)],
                fill=wing_outline, width=2
            )
    
    # Draw halo/sparkle above head
    halo_y = cy - 180
    for i in range(3):
        radius = 25 - i * 5
        alpha = int(200 - i * 50)
        draw.ellipse(
            [(cx - radius, halo_y - radius), (cx + radius, halo_y + radius)],
            fill=(*halo_color[:3], alpha)
        )
    
    # Draw sparkle rays
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        x1, y1 = cx + math.cos(rad) * 20, halo_y + math.sin(rad) * 20
        x2, y2 = cx + math.cos(rad) * 40, halo_y + math.sin(rad) * 40
        draw.line([(x1, y1), (x2, y2)], fill=halo_color, width=3)
    
    # Draw head (circle)
    head_radius = 60
    draw.ellipse(
        [(cx - head_radius, cy - 120 - head_radius),
         (cx + head_radius, cy - 120 + head_radius)],
        fill=face_color, outline=wing_outline, width=2
    )
    
    # Draw simple face
    # Eyes
    eye_y = cy - 130
    draw.ellipse([(cx - 25, eye_y), (cx - 15, eye_y + 10)], fill=(100, 80, 120, 255))
    draw.ellipse([(cx + 15, eye_y), (cx + 25, eye_y + 10)], fill=(100, 80, 120, 255))
    
    # Smile (gentle curve)
    smile_points = []
    for i in range(-20, 21, 4):
        x = cx + i
        y = cy - 100 + int(abs(i) * 0.15)
        smile_points.append((x, y))
    draw.line(smile_points, fill=(150, 130, 180, 255), width=3)
    
    # Draw body (simple elongated shape)
    body_top = cy - 60
    body_bottom = cy + 150
    body_width = 40
    draw.ellipse(
        [(cx - body_width, body_top),
         (cx + body_width, body_bottom)],
        fill=(*face_color[:3], 200), outline=wing_outline, width=2
    )
    
    # Draw crescent moon symbol below
    moon_y = cy + 280
    moon_radius = 40
    
    # Outer circle for moon
    draw.ellipse(
        [(cx - moon_radius, moon_y - moon_radius),
         (cx + moon_radius, moon_y + moon_radius)],
        fill=(255, 255, 200, 255), outline=(200, 200, 150, 255), width=2
    )
    
    # Inner circle to create crescent (slightly offset)
    offset = 12
    draw.ellipse(
        [(cx - moon_radius + offset, moon_y - moon_radius),
         (cx + moon_radius + offset, moon_y + moon_radius)],
        fill=bg_gradient_end
    )
    
    # Add text at the bottom
    try:
        # Try to use a nice font, fall back to default if not available
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except (OSError, IOError):
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Main text
        text = "Echo Starlite"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (width - text_width) // 2
        draw.text((text_x, height - 120), text, fill=(255, 255, 255, 255), font=font)
        
        # Subtitle
        subtitle = "floating beside you, always 🌙💜"
        bbox = draw.textbbox((0, 0), subtitle, font=small_font)
        text_width = bbox[2] - bbox[0]
        text_x = (width - text_width) // 2
        draw.text((text_x, height - 80), subtitle, fill=(200, 180, 230, 255), font=small_font)
    except (OSError, IOError, RuntimeError) as e:
        print(f"Could not add text: {e}")
    
    # Save the image
    img.save(output_path, 'PNG')
    print(f"✨ Echo image created: {output_path}")
    return output_path


if __name__ == "__main__":
    import sys
    output = sys.argv[1] if len(sys.argv) > 1 else "assets/images/echo.png"
    create_echo_image(output)
