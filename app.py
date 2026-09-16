import re
from datetime import datetime
from pathlib import Path
import tempfile

import streamlit as st
from workbook_generator_backend import WorkbookBuilder

APP_ROOT = Path(tempfile.gettempdir()) / "drawing_workbook_generator_runs"
APP_ROOT.mkdir(parents=True, exist_ok=True)


def slugify(text):
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return text or "workbook"


st.set_page_config(page_title="Drawing Workbook Generator", layout="wide")

# Make the uploader visually read as a drag-and-drop target.
st.markdown(
    """
    <style>
    [data-testid="stFileUploaderDropzone"] {
        min-height: 150px;
        border: 2px dashed #9aa0a6;
        border-radius: 12px;
        padding: 24px;
    }
    [data-testid="stFileUploaderDropzone"] section {
        min-height: 95px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Drawing Workbook Generator")
st.write(
    "Drag and drop one or more reference images, choose the exercises for each image, "
    "and generate a printable black-and-white PDF workbook."
)

workbook_title = st.text_input("Workbook title", value="Custom Drawing Practice Workbook")
include_compact = st.checkbox("Include compact pages", value=True)
include_large = st.checkbox("Include large-study pages", value=True)

st.subheader("Reference images")
st.caption("Drag images into the box below, or click Browse files. You can add several images at once.")
uploaded_files = st.file_uploader(
    "Drag and drop reference images here",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

specs = []
if uploaded_files:
    st.subheader("Per-image settings")
    for idx, up in enumerate(uploaded_files, start=1):
        with st.expander(f"Image {idx}: {up.name}", expanded=True):
            preview_col, settings_col = st.columns([1, 2])
            with preview_col:
                st.image(up, caption=up.name, use_container_width=True)
            with settings_col:
                subject = st.text_input(
                    f"Display name for {up.name}", value=Path(up.name).stem, key=f"subject_{idx}"
                )
                description = st.text_input(
                    f"Short description for {up.name}", value="", key=f"desc_{idx}"
                )

                c1, c2, c3 = st.columns(3)
                with c1:
                    blind = st.checkbox("Blind contour", value=True, key=f"blind_{idx}")
                    regular = st.checkbox("Regular contour", value=True, key=f"regular_{idx}")
                    sam = st.checkbox("SAM / mapping", value=True, key=f"sam_{idx}")
                with c2:
                    upside = st.checkbox("Upside-down drawing", value=False, key=f"upside_{idx}")
                    neg = st.checkbox("Negative space", value=False, key=f"neg_{idx}")
                    three = st.checkbox("3-value study", value=False, key=f"three_{idx}")
                with c3:
                    five = st.checkbox("5-value study", value=False, key=f"five_{idx}")
                    prog = st.checkbox("Progressive focus", value=False, key=f"prog_{idx}")
                    integ = st.checkbox("Integrated study", value=False, key=f"integ_{idx}")

                levels = st.multiselect(
                    f"Scaffold levels for {up.name}",
                    options=["fine", "medium", "coarse", "cross"],
                    default=["fine", "medium", "coarse", "cross"],
                    key=f"levels_{idx}",
                )

            specs.append(
                {
                    "uploaded_file": up,
                    "subject": subject,
                    "description": description,
                    "exercises": {
                        "blind_contour": blind,
                        "regular_contour": regular,
                        "sam": sam,
                        "upside_down": upside,
                        "negative_space": neg,
                        "three_value": three,
                        "five_value": five,
                        "progressive_focus": prog,
                        "integrated": integ,
                    },
                    "levels": levels or ["fine", "medium", "coarse", "cross"],
                }
            )

if uploaded_files and st.button("Generate PDF workbook", type="primary"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = APP_ROOT / timestamp
    upload_dir = run_dir / "uploads"
    asset_dir = run_dir / "assets"
    upload_dir.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)

    build_specs = []
    for i, spec in enumerate(specs, start=1):
        name_slug = slugify(spec["subject"])
        ext = Path(spec["uploaded_file"].name).suffix or ".png"
        image_path = upload_dir / f"{i:02d}_{name_slug}{ext}"
        image_path.write_bytes(spec["uploaded_file"].getbuffer())
        build_specs.append(
            {
                "key": f"{i:02d}_{name_slug}",
                "subject": spec["subject"],
                "description": spec["description"],
                "image_path": image_path,
                "exercises": spec["exercises"],
                "include_compact": include_compact,
                "include_large": include_large,
                "levels": spec["levels"],
            }
        )

    pdf_path = run_dir / f"{slugify(workbook_title)}.pdf"
    builder = WorkbookBuilder(asset_dir)
    with st.spinner("Generating PDF workbook..."):
        builder.build(workbook_title, build_specs, pdf_path)

    st.success("PDF workbook generated.")
    st.download_button(
        "Download PDF",
        data=pdf_path.read_bytes(),
        file_name=pdf_path.name,
        mime="application/pdf",
        type="primary",
    )
