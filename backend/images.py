"""Prepare uploads so Claid accepts them.

Claid rejects anything smaller than 256px on either side, and a tiny illustration also
gives the model very little to work with, so small images are scaled up before upload.
"""
import io

from PIL import Image

MIN_SIDE = 256
TARGET_SIDE = 768  # comfortable size for the generators
MAX_SIDE = 2048


def prepare(content: bytes, filename: str) -> tuple[bytes, str, str]:
    """Return (content, filename, content_type), upscaling the image if it is too small."""
    try:
        img = Image.open(io.BytesIO(content))
        img.load()
    except Exception:
        return content, filename, "image/png"  # not an image we can read; let Claid decide

    width, height = img.size
    short = min(width, height)
    long_side = max(width, height)

    if short >= MIN_SIDE and long_side <= MAX_SIDE:
        return content, filename, Image.MIME.get(img.format or "", "image/png")

    if short < MIN_SIDE:
        scale = TARGET_SIDE / short
    else:
        scale = MAX_SIDE / long_side

    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    img = img.convert("RGBA") if img.mode in ("P", "LA", "RGBA") else img.convert("RGB")
    img = img.resize(size, Image.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return buffer.getvalue(), f"{stem}.png", "image/png"
