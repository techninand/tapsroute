"""Validated reuse of owner-supplied, previously generated AI images."""
import json
from pathlib import Path
from .core import ROOT

LIBRARY = ROOT / "data" / "image-library.json"

def find_fallback_image(destination, category, library_path=LIBRARY):
    """Return only a destination-validated AI image from the approved library."""
    path = Path(library_path)
    if not path.exists():
        return None
    images = json.loads(path.read_text()).get("images", [])
    for image in images:
        categories = image.get("categories", [])
        if (
            image.get("destination", "").casefold() == destination.casefold()
            and image.get("validated_for_destination") is True
            and (not categories or category in categories)
            and image.get("model")
            and (image.get("image_path") or image.get("image_url"))
        ):
            return image
    return None
