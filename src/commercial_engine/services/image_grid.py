"""
services/image_grid.py
=======================
Creates composite image grids from character assets to serve as a unified
visual reference for video generation models (like Kling or Sora).
This ensures character consistency across shots.
"""

from PIL import Image
from typing import List
import math

def create_character_grid(image_paths: List[str], output_path: str, max_size: int = 1024) -> bool:
    """
    Combines up to 9 images into a grid containing character references.
    Returns True if successful, False otherwise.
    """
    if not image_paths:
        return False

    # Load images
    images = []
    for path in image_paths:
        try:
            img = Image.open(path).convert("RGB")
            images.append(img)
        except Exception as e:
            # Fallback or log error
            print(f"[ImageGrid] Error loading {path}: {e}")
            continue

    if not images:
        return False

    n = len(images)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)

    # Determine cell size
    cell_w = max_size // cols
    cell_h = max_size // rows

    # Create background canvas (black)
    grid_img = Image.new('RGB', (cols * cell_w, rows * cell_h), color=(0, 0, 0))

    for i, img in enumerate(images):
        # Resize image to fit cell while maintaining aspect ratio (cover/contain approach)
        # Here we just resize to fit inside the cell (contain)
        img.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
        
        # Center in cell
        x_offset = (cell_w - img.width) // 2
        y_offset = (cell_h - img.height) // 2
        
        col = i % cols
        row = i // cols
        
        paste_x = col * cell_w + x_offset
        paste_y = row * cell_h + y_offset
        
        grid_img.paste(img, (paste_x, paste_y))

    try:
        grid_img.save(output_path, quality=90)
        return True
    except Exception as e:
        print(f"[ImageGrid] Error saving grid to {output_path}: {e}")
        return False
