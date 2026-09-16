# Drawing Workbook Generator

A small Streamlit app for turning one or more reference images into printable black-and-white drawing-practice workbooks.

The workbook structure is designed around a repeatable learning sequence:

1. Blind contour — no grid
2. Regular contour — no grid
3. SAM / mapping — fine, medium, coarse, then center-cross scaffolds
4. Upside-down drawing — scaffold retained
5. Negative space — scaffold retained
6. 3-value study — optional
7. 5-value study — optional
8. Progressive focus — optional; one evolving drawing from blurred to sharp
9. Integrated study — optional; center-cross support

For supported exercises, the app can create compact same-page versions and larger practice pages. Drawing boxes follow the uploaded image's aspect ratio instead of forcing everything into a fixed 5×7 frame.

## What is in this repo

- `app.py` — Streamlit user interface
- `workbook_generator_backend.py` — image processing + DOCX/PDF workbook generation
- `example_build.py` — example build script using the current reference-image set
- `requirements.txt` — Python dependencies

## Easiest setup on Windows

### 1. Install Python

Install a current Python 3 release from python.org if you do not already have it. During installation, check **Add Python to PATH**.

### 2. Install LibreOffice

LibreOffice is used to convert the generated Word document to PDF. Install the desktop version of LibreOffice.

### 3. Download or clone this repository

With GitHub Desktop, choose **File → Clone repository** and select this repo.

### 4. Open a terminal in the repo folder

In GitHub Desktop, use **Repository → Open in Command Prompt / PowerShell** (wording can vary), or open PowerShell and `cd` into the repository folder.

### 5. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can skip activation and use `.\.venv\Scripts\python.exe` in the commands below.

### 6. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 7. Run the app

```powershell
python -m streamlit run app.py
```

A browser window should open with the workbook generator.

## Typical GitHub workflow as we revise it

1. Make or receive a revised file.
2. Replace the old file in your local repo folder.
3. Open GitHub Desktop.
4. Review the changed files.
5. Write a short summary such as `Improve grid progression and compact layout`.
6. Click **Commit to main**.
7. Click **Push origin**.

That gives every iteration a recoverable history. If a change turns out worse, an earlier version is still in Git history.

## Current limitations

- Crop approval is not interactive yet. The backend currently applies a conservative automatic crop.
- PDF export depends on LibreOffice being installed.
- The interface is functional rather than polished; crop preview/approval is a logical next feature.

## Recommended next development steps

- Interactive crop preview and approval for each uploaded image
- Per-image defaults/presets (simple object, organic form, full study)
- Preview estimated page count before generating
- Save/load workbook settings as a small JSON project file
- Later: optional color-study exercises
