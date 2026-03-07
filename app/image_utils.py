"""Image processing for question screenshots.

Handles resizing, compression, and base64 encoding of uploaded images.
Settings are stored in Streamlit session state and can be configured
from the Settings page.
"""

from __future__ import annotations

import base64
import io

from PIL import Image

# Default limits
DEFAULT_MAX_FILE_SIZE_KB = 500
DEFAULT_MAX_WIDTH_PX = 800
DEFAULT_JPEG_QUALITY = 85


def get_settings() -> dict:
    """Return current screenshot settings from session state or defaults."""
    try:
        import streamlit as st
        return {
            "max_file_size_kb": st.session_state.get("screenshot_max_kb", DEFAULT_MAX_FILE_SIZE_KB),
            "max_width_px": st.session_state.get("screenshot_max_width", DEFAULT_MAX_WIDTH_PX),
            "jpeg_quality": st.session_state.get("screenshot_jpeg_quality", DEFAULT_JPEG_QUALITY),
        }
    except Exception:
        return {
            "max_file_size_kb": DEFAULT_MAX_FILE_SIZE_KB,
            "max_width_px": DEFAULT_MAX_WIDTH_PX,
            "jpeg_quality": DEFAULT_JPEG_QUALITY,
        }


def process_screenshot(image_bytes: bytes) -> str:
    """Process an uploaded image: resize, compress, and return as base64 string.

    Returns a data URI string (e.g. "data:image/jpeg;base64,...").
    Raises ValueError if the image cannot be processed within the size limit.
    """
    settings = get_settings()
    max_kb = settings["max_file_size_kb"]
    max_width = settings["max_width_px"]
    quality = settings["jpeg_quality"]

    img = Image.open(io.BytesIO(image_bytes))

    # Convert RGBA/palette to RGB for JPEG
    if img.mode in ("RGBA", "P", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Resize if wider than max
    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)

    # Encode as JPEG, reducing quality if needed to stay under limit
    for q in range(quality, 19, -10):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=q, optimize=True)
        if buf.tell() <= max_kb * 1024:
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            return f"data:image/jpeg;base64,{b64}"

    raise ValueError(
        f"Image too large. Could not compress below {max_kb}KB even at minimum quality. "
        f"Try a smaller image or increase the size limit in Settings."
    )


def b64_to_bytes(data_uri: str) -> bytes:
    """Extract raw image bytes from a data URI string."""
    _, encoded = data_uri.split(",", 1)
    return base64.b64decode(encoded)
