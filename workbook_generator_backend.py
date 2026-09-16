from pathlib import Path
import math
import re

import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth

PAGE_W, PAGE_H = letter
MARGIN = 18
CONTENT_W = PAGE_W - 2 * MARGIN
FOOTER_Y = 9

INK = (0.14, 0.15, 0.17)
MUTED = (0.40, 0.42, 0.45)
PALE = (0.95, 0.96, 0.97)
LINE = (0.72, 0.74, 0.77)


class WorkbookBuilder:
    """Generate black-and-white drawing-practice workbooks directly as PDF."""

    def __init__(self, asset_dir):
        self.asset_dir = Path(asset_dir)
        self.asset_dir.mkdir(parents=True, exist_ok=True)
        self.cache = {}

    # ------------------------------------------------------------------
    # Image processing
    # ------------------------------------------------------------------
    def _content_crop_once(self, im, threshold=12, margin_frac=0.055):
        a = np.array(im.convert("L"))
        h, w = a.shape
        band = max(3, min(24, int(min(w, h) * 0.025)))
        border = np.concatenate(
            [a[:band, :].ravel(), a[-band:, :].ravel(), a[:, :band].ravel(), a[:, -band:].ravel()]
        )
        bg = int(np.median(border))
        mask = np.abs(a.astype(np.int16) - bg) > threshold
        row_counts = mask.sum(axis=1)
        col_counts = mask.sum(axis=0)
        rows = np.where(row_counts > max(2, int(w * 0.002)))[0]
        cols = np.where(col_counts > max(2, int(h * 0.002)))[0]
        if len(rows) == 0 or len(cols) == 0:
            return im
        y0, y1 = rows[0], rows[-1]
        x0, x1 = cols[0], cols[-1]
        cw, ch = x1 - x0 + 1, y1 - y0 + 1
        mx = max(8, int(cw * margin_frac))
        my = max(8, int(ch * margin_frac))
        x0 = max(0, x0 - mx)
        x1 = min(w - 1, x1 + mx)
        y0 = max(0, y0 - my)
        y1 = min(h - 1, y1 + my)
        if (x1 - x0 + 1) > 0.985 * w and (y1 - y0 + 1) > 0.985 * h:
            return im
        return im.crop((x0, y0, x1 + 1, y1 + 1))

    def load_crop(self, image_path):
        image_path = str(image_path)
        ck = ("crop", image_path)
        if ck in self.cache:
            return self.cache[ck].copy()
        im = Image.open(image_path).convert("L")
        im = self._content_crop_once(im, 12, 0.055)
        im2 = self._content_crop_once(im, 14, 0.075)
        if im2.width * im2.height >= 0.35 * im.width * im.height:
            im = im2
        long_side = max(im.size)
        if long_side < 1800:
            scale = 1800 / long_side
            im = im.resize(
                (max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                Image.Resampling.LANCZOS,
            )
        self.cache[ck] = im.copy()
        return im

    def image_ratio(self, image_path):
        im = self.load_crop(image_path)
        return im.width / im.height

    def grid_dims_for_ratio(self, ratio, level):
        if level == "cross":
            return None
        nlong = {"fine": 8, "medium": 5, "coarse": 3}[level]
        if ratio >= 1:
            cols = nlong
            rows = max(2, round(nlong / ratio))
        else:
            rows = nlong
            cols = max(2, round(nlong * ratio))
        return int(cols), int(rows)

    def overlay_scaffold(self, im, level, line=188):
        out = im.convert("L").copy()
        d = ImageDraw.Draw(out)
        w, h = out.size
        d.rectangle([1, 1, w - 2, h - 2], outline=138, width=3)
        if level is None or level == "none":
            return out
        if level == "cross":
            d.line([(w // 2, 0), (w // 2, h)], fill=line, width=3)
            d.line([(0, h // 2), (w, h // 2)], fill=line, width=3)
            return out
        cols, rows = self.grid_dims_for_ratio(w / h, level)
        for i in range(1, cols):
            x = round(w * i / cols)
            d.line([(x, 0), (x, h)], fill=line, width=3)
        for j in range(1, rows):
            y = round(h * j / rows)
            d.line([(0, y), (w, y)], fill=line, width=3)
        return out

    def blank_scaffold(self, ratio, level, long_px=1800):
        if ratio >= 1:
            w = long_px
            h = max(300, round(long_px / ratio))
        else:
            h = long_px
            w = max(300, round(long_px * ratio))
        return self.overlay_scaffold(Image.new("L", (w, h), 255), level)

    def quantize_values(self, im, n):
        x = ImageOps.autocontrast(im.convert("L"), cutoff=1)
        a = np.array(x)
        cuts = np.percentile(a.reshape(-1), np.linspace(0, 100, n + 1)[1:-1])
        idx = np.digitize(a, cuts)
        tones = np.linspace(30, 235, n).astype(np.uint8)
        return Image.fromarray(tones[idx], mode="L")

    def progressive(self, im, stage):
        """Four deliberately distinct focus stages."""
        x = ImageOps.autocontrast(im.convert("L"), cutoff=1)
        w, h = x.size
        long_side = max(w, h)
        if stage == 1:  # very blurred
            target = 32
            s = target / long_side
            sm = x.resize((max(8, int(w * s)), max(8, int(h * s))), Image.Resampling.BILINEAR)
            up = sm.resize((w, h), Image.Resampling.BICUBIC)
            return up.filter(ImageFilter.GaussianBlur(max(5, long_side / 150)))
        if stage == 2:  # medium blur
            target = 95
            s = target / long_side
            sm = x.resize((max(12, int(w * s)), max(12, int(h * s))), Image.Resampling.BILINEAR)
            up = sm.resize((w, h), Image.Resampling.BICUBIC)
            return up.filter(ImageFilter.GaussianBlur(max(2.5, long_side / 450)))
        if stage == 3:  # nearly sharp
            target = 500
            s = min(1, target / long_side)
            sm = x.resize((max(20, int(w * s)), max(20, int(h * s))), Image.Resampling.LANCZOS)
            up = sm.resize((w, h), Image.Resampling.BICUBIC)
            return up.filter(ImageFilter.GaussianBlur(max(0.5, long_side / 2400)))
        return x  # sharp

    def _safe_key(self, text):
        return re.sub(r"[^A-Za-z0-9_-]+", "_", str(text)).strip("_") or "image"

    def asset(self, image_path, key, kind="clear", level=None, upside=False):
        image_path = Path(image_path)
        ck = (str(image_path), key, kind, level, upside)
        if ck in self.cache:
            return self.cache[ck]
        im = self.load_crop(image_path)
        if upside:
            im = im.rotate(180)
        if kind == "clear":
            pass
        elif kind == "3value":
            im = self.quantize_values(im, 3)
        elif kind == "5value":
            im = self.quantize_values(im, 5)
        elif kind.startswith("focus"):
            im = self.progressive(im, int(kind[-1]))
        else:
            raise ValueError(kind)
        im = self.overlay_scaffold(im, level)
        p = self.asset_dir / f"{self._safe_key(key)}_{kind}_{level or 'none'}{'_up' if upside else ''}.png"
        if not p.exists():
            im.save(p, optimize=True)
        self.cache[ck] = p
        return p

    def blank_asset(self, image_path, key, level=None):
        ck = ("blank", str(image_path), key, level)
        if ck in self.cache:
            return self.cache[ck]
        im = self.blank_scaffold(self.image_ratio(image_path), level)
        p = self.asset_dir / f"blank_{self._safe_key(key)}_{level or 'none'}.png"
        if not p.exists():
            im.save(p, optimize=True)
        self.cache[ck] = p
        return p

    # ------------------------------------------------------------------
    # PDF drawing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _set_rgb(c, rgb):
        c.setFillColorRGB(*rgb)

    @staticmethod
    def _fit_box(ratio, max_w, max_h):
        if ratio >= 1:
            w = max_w
            h = w / ratio
            if h > max_h:
                h = max_h
                w = h * ratio
        else:
            h = max_h
            w = h * ratio
            if w > max_w:
                w = max_w
                h = w / ratio
        return w, h

    @staticmethod
    def _wrap(text, font, size, width):
        words = str(text).split()
        if not words:
            return [""]
        lines = []
        cur = words[0]
        for word in words[1:]:
            test = cur + " " + word
            if stringWidth(test, font, size) <= width:
                cur = test
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
        return lines

    def _footer(self, c):
        self._set_rgb(c, MUTED)
        c.setFont("Helvetica", 6.5)
        c.drawRightString(PAGE_W - MARGIN, FOOTER_Y, "Print at 100% / Actual size")

    def _finish_page(self, c):
        self._footer(c)
        c.showPage()

    def _header(self, c, subject, title, subtitle=None):
        y = PAGE_H - MARGIN - 4
        self._set_rgb(c, MUTED)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(MARGIN, y, subject.upper())
        y -= 19
        self._set_rgb(c, INK)
        c.setFont("Times-Roman", 18)
        c.drawString(MARGIN, y, title)
        y -= 16
        if subtitle:
            self._set_rgb(c, MUTED)
            c.setFont("Helvetica", 8)
            for line in self._wrap(subtitle, "Helvetica", 8, CONTENT_W):
                c.drawString(MARGIN, y, line)
                y -= 10
        return y - 3

    def _task_box(self, c, text, y, width=CONTENT_W):
        font, size = "Helvetica", 7.7
        lines = self._wrap(text, font, size, width - 12)
        h = max(20, 8 + len(lines) * 9)
        c.setFillColorRGB(*PALE)
        c.roundRect(MARGIN, y - h, width, h, 3, fill=1, stroke=0)
        self._set_rgb(c, MUTED)
        c.setFont(font, size)
        ty = y - 12
        for line in lines:
            c.drawString(MARGIN + 6, ty, line)
            ty -= 9
        return y - h - 6

    def _label(self, c, text, x, y, width, center=True):
        self._set_rgb(c, MUTED)
        c.setFont("Helvetica-Bold", 6.8)
        if center:
            c.drawCentredString(x + width / 2, y, text)
        else:
            c.drawString(x, y, text)

    def _draw_image(self, c, path, x, y, w, h):
        c.drawImage(ImageReader(str(path)), x, y, width=w, height=h, preserveAspectRatio=False, mask="auto")

    def _pair(self, c, left_path, right_path, y_top, ratio, max_h, max_w_each=270, gap=14,
              left_label="REFERENCE", right_label="YOUR DRAWING"):
        w, h = self._fit_box(ratio, max_w_each, max_h)
        total = w * 2 + gap
        x0 = (PAGE_W - total) / 2
        label_y = y_top - 2
        self._label(c, left_label, x0, label_y, w)
        self._label(c, right_label, x0 + w + gap, label_y, w)
        img_y = label_y - 8 - h
        self._draw_image(c, left_path, x0, img_y, w, h)
        self._draw_image(c, right_path, x0 + w + gap, img_y, w, h)
        return img_y

    # ------------------------------------------------------------------
    # Exercise pages
    # ------------------------------------------------------------------
    def dual_observation_page(self, c, image_path, key, subject, include_blind=True, include_regular=True):
        blocks = []
        if include_blind:
            blocks.append((
                "Blind contour",
                "Look at the reference, not the paper. Move slowly around the contour. Accuracy is not the goal.",
            ))
        if include_regular:
            blocks.append((
                "Regular contour",
                "Observe the outside contour and major inner edges. No grid: this is an observation exercise, not a placement test.",
            ))
        title = "Blind contour + regular contour" if len(blocks) == 2 else blocks[0][0]
        subtitle = "Two observation exercises on one page. No grid." if len(blocks) == 2 else "Observation exercise. No grid."
        y = self._header(c, subject, title, subtitle)
        ratio = self.image_ratio(image_path)
        ref = self.asset(image_path, key, "clear", None, False)
        draw = self.blank_asset(image_path, key, None)

        if len(blocks) == 1:
            _, task = blocks[0]
            y = self._task_box(c, task, y)
            self._pair(c, ref, draw, y - 2, ratio, max_h=520, max_w_each=275)
        else:
            available = y - 30 - FOOTER_Y
            each_h = max(155, min(230, (available - 100) / 2))
            for i, (name, task) in enumerate(blocks):
                self._set_rgb(c, INK)
                c.setFont("Times-Roman", 13)
                c.drawString(MARGIN, y, name)
                y -= 5
                y = self._task_box(c, task, y)
                bottom = self._pair(c, ref, draw, y - 2, ratio, max_h=each_h, max_w_each=272)
                y = bottom - 18
        self._finish_page(c)

    def sampler_page(self, c, image_path, key, subject, skill, task, kind="clear", upside=False,
                     levels=("fine", "medium", "coarse", "cross")):
        y = self._header(c, subject, f"{skill} - scaffold sampler",
                         "Four quick versions on one page. The cross is another support level, not a test.")
        y = self._task_box(c, task, y)
        ratio = self.image_ratio(image_path)
        grid_gap = 8
        cell_w = (CONTENT_W - grid_gap) / 2
        cell_h = (y - FOOTER_Y - 18 - grid_gap) / 2
        top_y = y - 3

        for idx, lev in enumerate(levels):
            row, col = divmod(idx, 2)
            x = MARGIN + col * (cell_w + grid_gap)
            cell_top = top_y - row * (cell_h + grid_gap)
            cell_bottom = cell_top - cell_h
            c.setStrokeColorRGB(*LINE)
            c.setLineWidth(0.5)
            c.rect(x, cell_bottom, cell_w, cell_h, fill=0, stroke=1)
            self._set_rgb(c, MUTED)
            c.setFont("Helvetica-Bold", 7.5)
            c.drawCentredString(x + cell_w / 2, cell_top - 11, lev.upper())
            inner_gap = 8
            iw_max = (cell_w - 20 - inner_gap) / 2
            ih_max = cell_h - 36
            iw, ih = self._fit_box(ratio, iw_max, ih_max)
            pair_w = iw * 2 + inner_gap
            px = x + (cell_w - pair_w) / 2
            py = cell_bottom + 8
            self._label(c, "REF", px, py + ih + 5, iw)
            self._label(c, "DRAW", px + iw + inner_gap, py + ih + 5, iw)
            self._draw_image(c, self.asset(image_path, key, kind, lev, upside), px, py, iw, ih)
            self._draw_image(c, self.blank_asset(image_path, key, lev), px + iw + inner_gap, py, iw, ih)
        self._finish_page(c)

    def large_pair(self, c, image_path, key, subject, title, task, kind="clear", level=None, upside=False):
        ratio = self.image_ratio(image_path)
        paths = [
            ("REFERENCE", self.asset(image_path, key, kind, level, upside)),
            ("DRAWING", self.blank_asset(image_path, key, level)),
        ]
        for label, path in paths:
            y = self._header(c, subject, title, f"Large study - {label.lower()}")
            y = self._task_box(c, task, y)
            self._label(c, label, MARGIN, y - 1, CONTENT_W)
            max_h = y - 18 - FOOTER_Y
            w, h = self._fit_box(ratio, CONTENT_W, max_h)
            x = (PAGE_W - w) / 2
            img_y = FOOTER_Y + 15 + max(0, (max_h - h) / 2)
            self._draw_image(c, path, x, img_y, w, h)
            self._finish_page(c)

    def compact_pair_page(self, c, image_path, key, subject, title, task, kind="clear", level=None, upside=False):
        y = self._header(c, subject, title)
        y = self._task_box(c, task, y)
        ratio = self.image_ratio(image_path)
        self._pair(
            c,
            self.asset(image_path, key, kind, level, upside),
            self.blank_asset(image_path, key, level),
            y - 3,
            ratio,
            max_h=y - FOOTER_Y - 24,
            max_w_each=272,
        )
        self._finish_page(c)

    def value_sequence(self, c, image_path, key, subject, include_compact=True, include_large=True,
                       do3=True, do5=True):
        if do3:
            if include_compact:
                self.compact_pair_page(c, image_path, key, subject, "3-value study - compact",
                    "Reduce the image to three value families only: dark, middle, light. Ignore detail.",
                    kind="3value", level="medium")
            if include_large:
                self.large_pair(c, image_path, key, subject, "3-value study - large",
                    "Use the same three value families at a larger scale. Keep the medium grid for placement.",
                    kind="3value", level="medium")
        if do5:
            if include_compact:
                self.compact_pair_page(c, image_path, key, subject, "5-value study - compact",
                    "Use five value families from darkest to lightest. Keep the big masses unified.",
                    kind="5value", level="medium")
            if include_large:
                self.large_pair(c, image_path, key, subject, "5-value study - large",
                    "Repeat at a larger scale. Add intermediate values only after the large masses read.",
                    kind="5value", level="medium")

    def progressive_focus(self, c, image_path, key, subject):
        ratio = self.image_ratio(image_path)
        y = self._header(c, subject, "Progressive focus - one evolving drawing",
                         "Use this same sheet through all four reference stages.")
        y = self._task_box(c,
            "Do not restart. Begin with the largest masses, then add only what each sharper reference genuinely reveals. The coarse grid stays so placement is not the challenge.", y)
        self._label(c, "WORKING DRAWING", MARGIN, y - 1, CONTENT_W)
        max_h = y - 18 - FOOTER_Y
        w, h = self._fit_box(ratio, CONTENT_W, max_h)
        self._draw_image(c, self.blank_asset(image_path, key, "coarse"), (PAGE_W - w) / 2, FOOTER_Y + 15 + (max_h - h)/2, w, h)
        self._finish_page(c)

        stage_names = {1: "Very blurred", 2: "Medium blur", 3: "Nearly sharp", 4: "Sharp"}
        stage_tasks = {
            1: "Place only the biggest masses and overall direction.",
            2: "Add major divisions, overlaps, and broad edge changes.",
            3: "Refine principal contours and secondary relationships.",
            4: "Add selected detail only where it helps the drawing.",
        }
        for st in range(1, 5):
            y = self._header(c, subject, f"Progressive focus - {stage_names[st]}",
                             f"Stage {st} of 4 - continue on the same drawing")
            y = self._task_box(c, stage_tasks[st], y)
            self._label(c, "REFERENCE", MARGIN, y - 1, CONTENT_W)
            max_h = y - 18 - FOOTER_Y
            w, h = self._fit_box(ratio, CONTENT_W, max_h)
            self._draw_image(c, self.asset(image_path, key, f"focus{st}", "coarse"),
                             (PAGE_W - w)/2, FOOTER_Y + 15 + (max_h - h)/2, w, h)
            self._finish_page(c)

    def final_integrated(self, c, image_path, key, subject, include_compact=True, include_large=True):
        if include_compact:
            self.compact_pair_page(c, image_path, key, subject, "Integrated study - center cross",
                "Use the center cross as a light placement scaffold. Apply whichever habits helped: envelope, landmarks, negative space, then values.",
                kind="clear", level="cross")
        if include_large:
            self.large_pair(c, image_path, key, subject, "Integrated study - center cross",
                "Repeat larger with only the center cross. This is still supported; it is not a blank-page test.",
                kind="clear", level="cross")

    def subject_core(self, c, spec):
        image_path = spec["image_path"]
        key = spec["key"]
        subject = spec["subject"]
        exercises = spec.get("exercises", {})
        include_compact = spec.get("include_compact", True)
        include_large = spec.get("include_large", True)
        levels = spec.get("levels", ["fine", "medium", "coarse", "cross"])

        if exercises.get("blind_contour") or exercises.get("regular_contour"):
            self.dual_observation_page(
                c, image_path, key, subject,
                include_blind=exercises.get("blind_contour", False),
                include_regular=exercises.get("regular_contour", False),
            )

        if exercises.get("sam"):
            if include_compact:
                self.sampler_page(c, image_path, key, subject, "SAM / mapping",
                    "Locate top, bottom, left, right, then major intersections and angles before drawing. Use the grid deliberately.")
            if include_large:
                for lev in [lv for lv in ["fine", "medium", "coarse", "cross"] if lv in levels]:
                    self.large_pair(c, image_path, key, subject, f"SAM / mapping - {lev} scaffold",
                        "Map the envelope and landmarks first. Use only as much of the scaffold as is helpful.",
                        level=lev)

        if exercises.get("upside_down"):
            if include_compact:
                self.sampler_page(c, image_path, key, subject, "Upside-down drawing",
                    "Treat the image as shapes, angles, and distances rather than naming the object. Keep placement support.",
                    upside=True)
            if include_large:
                for lev in [lv for lv in ["fine", "medium", "coarse"] if lv in levels]:
                    self.large_pair(c, image_path, key, subject, f"Upside down - {lev} scaffold",
                        "Copy the upside-down image as shapes and distances. The scaffold is intentionally retained.",
                        level=lev, upside=True)

        if exercises.get("negative_space"):
            if include_compact:
                self.sampler_page(c, image_path, key, subject, "Negative space",
                    "Draw the empty shapes around and between the object parts. Let the object appear from those spaces.")
            if include_large:
                for lev in [lv for lv in ["fine", "medium", "coarse"] if lv in levels]:
                    self.large_pair(c, image_path, key, subject, f"Negative space - {lev} scaffold",
                        "Use the scaffold to place the empty shapes. Changing what you observe should not also remove placement support.",
                        level=lev)

        if exercises.get("three_value") or exercises.get("five_value"):
            self.value_sequence(
                c, image_path, key, subject,
                include_compact=include_compact,
                include_large=include_large,
                do3=exercises.get("three_value", False),
                do5=exercises.get("five_value", False),
            )

        if exercises.get("progressive_focus"):
            self.progressive_focus(c, image_path, key, subject)

        if exercises.get("integrated"):
            self.final_integrated(c, image_path, key, subject, include_compact, include_large)

    def build(self, workbook_title, specs, output_pdf):
        """Build the workbook directly as a PDF. No LibreOffice or DOCX is required."""
        output_pdf = Path(output_pdf)
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(output_pdf), pagesize=letter, pageCompression=1)
        c.setTitle(workbook_title)
        for spec in specs:
            self.subject_core(c, spec)
        c.save()
        return output_pdf
