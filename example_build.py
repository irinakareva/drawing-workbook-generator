"""Minimal example: generate a PDF workbook from one image."""

from pathlib import Path
from workbook_generator_backend import WorkbookBuilder

HERE = Path(__file__).resolve().parent
IMAGE = HERE / "example_reference.jpg"  # replace with your own image
OUT_DIR = HERE / "example_output"
OUT_DIR.mkdir(exist_ok=True)

specs = [
    {
        "key": "example",
        "subject": "EXAMPLE",
        "description": "Example reference",
        "image_path": IMAGE,
        "include_compact": True,
        "include_large": True,
        "levels": ["fine", "medium", "coarse", "cross"],
        "exercises": {
            "blind_contour": True,
            "regular_contour": True,
            "sam": True,
            "upside_down": True,
            "negative_space": True,
            "three_value": True,
            "five_value": True,
            "progressive_focus": True,
            "integrated": True,
        },
    }
]

builder = WorkbookBuilder(OUT_DIR / "assets")
builder.build("Example Drawing Workbook", specs, OUT_DIR / "example_workbook.pdf")
print(OUT_DIR / "example_workbook.pdf")
