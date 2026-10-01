"""
Generate application icons (PNG and ICO) for the Tailscale File Uploader.
"""

from pathlib import Path
from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

def create_tray_icon():
    # 64x64 high-resolution icon
    size = (64, 64)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Outer rounded badge (Tailscale deep blue)
    # Circle base
    draw.ellipse([4, 4, 60, 60], fill=(24, 32, 44, 255), outline=(59, 130, 246, 255), width=2)

    # Cloud / Tray Tray Upload Arrow (Bright Cyan/Blue)
    # Arrow stem
    draw.rectangle([30, 24, 34, 44], fill=(56, 189, 248, 255))
    # Arrow head (triangle)
    draw.polygon([(32, 14), (20, 26), (44, 26)], fill=(56, 189, 248, 255))
    # Horizontal base tray line
    draw.rectangle([20, 47, 44, 50], fill=(59, 130, 246, 255))

    png_path = STATIC_DIR / "tray_icon.png"
    ico_path = STATIC_DIR / "tray_icon.ico"

    image.save(png_path, format="PNG")
    image.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    return png_path, ico_path

if __name__ == "__main__":
    png, ico = create_tray_icon()
    print(f"Generated icons: {png}, {ico}")
