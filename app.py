import re
import tempfile
import zipfile
import hashlib
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image
from streamlit_cropper import st_cropper
from streamlit_paste_button import paste_image_button

from workbook_generator_backend import WorkbookBuilder

APP_ROOT = Path(tempfile.gettempdir()) / "drawing_workbook_generator_runs"
APP_ROOT.mkdir(parents=True, exist_ok=True)
ASSET_DIR = Path(__file__).resolve().parent / "assets"


@dataclass
class MemoryImageUpload:
    """Minimal UploadedFile-like wrapper for clipboard images."""
    name: str
    data: bytes

    def getvalue(self):
        return self.data


def clipboard_upload_from_pil(image, name):
    buf = BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    return MemoryImageUpload(name=name, data=buf.getvalue())


def slugify(text):
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(text)).strip("_")
    return text or "workbook"


def pil_from_upload(uploaded_file):
    return Image.open(BytesIO(uploaded_file.getvalue())).convert("RGB")


def merged_suffix(specs):
    stems = [slugify(Path(s["uploaded_file"].name).stem) for s in specs]
    if len(stems) <= 3:
        return "__".join(stems)
    return f"{len(stems)}_images"


st.set_page_config(page_title="Drawing Workbook Generator", layout="wide")

st.markdown(
    """
    <style>
    [data-testid="stFileUploaderDropzone"] {
        min-height: 165px;
        border: 2px dashed #9aa0a6;
        border-radius: 12px;
        padding: 24px;
    }
    [data-testid="stFileUploaderDropzone"] section {
        min-height: 105px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Drawing Workbook Generator")
st.write(
    "Drag and drop one or more reference images, optionally crop/frame each one, "
    "choose the exercises, and generate printable black-and-white PDF workbooks."
)

with st.expander("About this tool"):
    st.markdown(
        """
This tool turns a reference image into a **structured drawing-practice workbook** rather than asking you to jump straight from looking at an image to drawing it unsupported. The same perceptual skills can be repeated across different references while placement support fades gradually.

**Typical exercise sequence**

1. **Blind contour** — observation only; no grid.
2. **Regular contour** — observed edges and major internal contours; no grid.
3. **SAM / mapping** — sighting, angles, and mapping with scaffold support.
4. **Upside-down drawing** — reduces object-labeling while keeping placement support.
5. **Negative space** — draw the empty shapes around and between forms.
6. **3-value study** — simplify to dark, middle, and light.
7. **5-value study** — develop the value structure further.
8. **Progressive focus** — build one drawing from very blurred to sharp references.
9. **Integrated study** — bring the process together with only a light center-cross scaffold.

For supported exercises, the scaffold can fade **fine grid → medium grid → coarse grid → center cross** instead of disappearing all at once. You can generate compact practice pages, larger studies, or both.
        """
    )

    overview = ASSET_DIR / "app_overview.png"
    contour = ASSET_DIR / "contour_example.jpg"
    scaffold = ASSET_DIR / "scaffold_progression.jpg"

    if overview.exists():
        st.image(str(overview), caption="Workbook generator overview", use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        if contour.exists():
            st.image(str(contour), caption="Contour exercises: observation without a grid", use_container_width=True)
    with col2:
        if scaffold.exists():
            st.image(str(scaffold), caption="Placement support fades gradually", use_container_width=True)

    st.markdown(
        """
**Image input**

- File upload / drag-and-drop: **PNG, JPG/JPEG, WEBP**
- Clipboard: paste a screenshot or copied image directly into the app; clipboard images are imported as PNG.
- On Windows, **Win + Shift + S** puts a screen clipping on the clipboard, so it can be added without saving a file first.
        """
    )

    st.markdown(
        "[Full project details and setup instructions on GitHub](https://github.com/irinakareva/drawing-workbook-generator)"
    )

workbook_title = st.text_input("Workbook title", value="Custom Drawing Practice Workbook")
include_compact = st.checkbox("Include compact pages", value=True)
include_large = st.checkbox("Include large-study pages", value=True)
output_mode = st.radio(
    "Output",
    ["One merged workbook", "Separate workbook for each image", "Both"],
    index=0,
    horizontal=True,
)

st.subheader("Reference images")
st.caption(
    "Drag files into the box, browse for files, or paste a screenshot/image from your clipboard. "
    "Supported files: PNG, JPG/JPEG, WEBP. Clipboard images are imported as PNG."
)

uploaded_files = st.file_uploader(
    "Drag and drop reference images here",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

if "pasted_images" not in st.session_state:
    st.session_state.pasted_images = []

paste_col, clear_col = st.columns([1, 1])
with paste_col:
    paste_result = paste_image_button(
        label="Paste screenshot/image from clipboard",
        key="clipboard_paste_button",
        errors="raise",
    )

if paste_result.image_data is not None:
    buf = BytesIO()
    paste_result.image_data.convert("RGB").save(buf, format="PNG")
    img_bytes = buf.getvalue()
    digest = hashlib.sha256(img_bytes).hexdigest()
    known = {item["digest"] for item in st.session_state.pasted_images}
    if digest not in known:
        n = len(st.session_state.pasted_images) + 1
        st.session_state.pasted_images.append(
            {
                "name": f"clipboard_{n:02d}.png",
                "data": img_bytes,
                "digest": digest,
            }
        )
        st.rerun()

with clear_col:
    if st.session_state.pasted_images:
        if st.button("Clear pasted images"):
            st.session_state.pasted_images = []
            st.rerun()

pasted_uploads = [
    MemoryImageUpload(name=item["name"], data=item["data"])
    for item in st.session_state.pasted_images
]
all_images = list(uploaded_files or []) + pasted_uploads

if st.session_state.pasted_images:
    st.caption(
        f"{len(st.session_state.pasted_images)} clipboard image(s) added. "
        "Copy another screenshot/image and click the paste button again to add more."
    )

specs = []
if all_images:
    st.subheader("Per-image settings")
    for idx, up in enumerate(all_images, start=1):
        with st.expander(f"Image {idx}: {up.name}", expanded=True):
            original_img = pil_from_upload(up)

            subject = st.text_input(
                f"Display name for {up.name}", value=Path(up.name).stem, key=f"subject_{idx}"
            )
            description = st.text_input(
                f"Short description for {up.name}", value="", key=f"desc_{idx}"
            )

            st.markdown("**Image framing**")
            framing_mode = st.radio(
                f"Framing mode for {up.name}",
                ["Auto frame", "Crop manually", "Use full image exactly"],
                index=0,
                horizontal=True,
                key=f"framing_{idx}",
                label_visibility="collapsed",
            )

            crop_image = None
            crop_box = None
            if framing_mode == "Crop manually":
                crop_left, crop_right = st.columns([1.45, 1])
                with crop_left:
                    aspect_choice = st.selectbox(
                        "Crop aspect ratio",
                        ["Free", "1:1", "4:5", "3:4", "4:3", "16:9"],
                        index=0,
                        key=f"aspect_{idx}",
                    )
                    aspect_map = {
                        "Free": None,
                        "1:1": (1, 1),
                        "4:5": (4, 5),
                        "3:4": (3, 4),
                        "4:3": (4, 3),
                        "16:9": (16, 9),
                    }
                    crop_image, crop_box = st_cropper(
                        original_img,
                        realtime_update=True,
                        box_color="#ff4b4b",
                        aspect_ratio=aspect_map[aspect_choice],
                        return_type="both",
                        key=f"cropper_{idx}",
                        should_resize_image=True,
                        stroke_width=3,
                    )
                with crop_right:
                    st.caption("Crop preview")
                    st.image(crop_image, use_container_width=True)
                    if crop_box:
                        st.caption(
                            f"{crop_image.width} x {crop_image.height} px · "
                            f"crop x={crop_box['left']}, y={crop_box['top']}"
                        )
            else:
                preview_col, note_col = st.columns([1, 1.3])
                with preview_col:
                    st.image(original_img, caption=up.name, use_container_width=True)
                with note_col:
                    if framing_mode == "Auto frame":
                        st.caption(
                            "The generator will trim obvious unused outer background before sizing the exercise boxes."
                        )
                    else:
                        st.caption(
                            "The entire uploaded image will be preserved exactly, including its current edges and whitespace."
                        )

            st.markdown("**Exercises**")
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
                    "framing_mode": framing_mode,
                    "crop_image": crop_image.copy() if crop_image is not None else None,
                }
            )

if all_images and st.button("Generate workbook", type="primary"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir = APP_ROOT / timestamp
    upload_dir = run_dir / "uploads"
    asset_dir = run_dir / "assets"
    upload_dir.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)

    build_specs = []
    for i, spec in enumerate(specs, start=1):
        name_slug = slugify(spec["subject"])
        framing_mode = spec["framing_mode"]
        preserve_crop = False

        if framing_mode == "Crop manually":
            image_path = upload_dir / f"{i:02d}_{name_slug}_crop.png"
            spec["crop_image"].save(image_path, format="PNG")
            preserve_crop = True
        elif framing_mode == "Use full image exactly":
            image_path = upload_dir / f"{i:02d}_{name_slug}_full.png"
            pil_from_upload(spec["uploaded_file"]).save(image_path, format="PNG")
            preserve_crop = True
        else:
            ext = Path(spec["uploaded_file"].name).suffix.lower() or ".png"
            image_path = upload_dir / f"{i:02d}_{name_slug}{ext}"
            image_path.write_bytes(spec["uploaded_file"].getvalue())

        build_specs.append(
            {
                "key": f"{i:02d}_{name_slug}",
                "subject": spec["subject"],
                "description": spec["description"],
                "image_path": image_path,
                "preserve_crop": preserve_crop,
                "exercises": spec["exercises"],
                "include_compact": include_compact,
                "include_large": include_large,
                "levels": spec["levels"],
            }
        )

    st.caption("Generating for: " + ", ".join(s["subject"] for s in build_specs))

    merged_pdf_path = None
    separate_pdf_paths = []

    with st.spinner("Generating workbook..."):
        # Use independent builders so each output gets a clean image/cache state.
        if output_mode in ["One merged workbook", "Both"]:
            merged_name = f"{slugify(workbook_title)}__merged__{merged_suffix(specs)}.pdf"
            merged_pdf_path = run_dir / merged_name
            WorkbookBuilder(run_dir / "assets_merged").build(workbook_title, build_specs, merged_pdf_path)

        if output_mode in ["Separate workbook for each image", "Both"]:
            for idx, (source_spec, build_spec) in enumerate(zip(specs, build_specs), start=1):
                original_stem = slugify(Path(source_spec["uploaded_file"].name).stem)
                subject_stem = slugify(source_spec["subject"])
                name_bits = [slugify(workbook_title), original_stem]
                if subject_stem.lower() != original_stem.lower():
                    name_bits.append(subject_stem)
                single_pdf_path = run_dir / ("__".join(name_bits) + ".pdf")
                single_title = f"{workbook_title} - {source_spec['subject']}"
                WorkbookBuilder(run_dir / f"assets_{idx:02d}").build(single_title, [build_spec], single_pdf_path)
                separate_pdf_paths.append(single_pdf_path)

    st.success("Workbook generation complete.")

    if merged_pdf_path is not None and merged_pdf_path.exists():
        st.subheader("Merged workbook")
        st.download_button(
            "Download merged PDF",
            data=merged_pdf_path.read_bytes(),
            file_name=merged_pdf_path.name,
            mime="application/pdf",
            type="primary",
            key="download_merged_pdf",
        )

    if separate_pdf_paths:
        st.subheader("Separate workbooks")

        zip_path = run_dir / f"{slugify(workbook_title)}__separate_workbooks.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for pdf_path in separate_pdf_paths:
                zf.write(pdf_path, arcname=pdf_path.name)

        st.download_button(
            "Download all separate PDFs (ZIP)",
            data=zip_path.read_bytes(),
            file_name=zip_path.name,
            mime="application/zip",
            key="download_zip_all",
        )

        for pdf_path in separate_pdf_paths:
            st.download_button(
                f"Download {pdf_path.stem}",
                data=pdf_path.read_bytes(),
                file_name=pdf_path.name,
                mime="application/pdf",
                key=f"download_{pdf_path.stem}",
            )
