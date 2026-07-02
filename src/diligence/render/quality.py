"""Document quality tiers.

Week 2's extraction evals are stratified by quality: clean digital PDF vs
scanned vs photographed. Degradation is deterministic per (file name, tier)
so eval runs are reproducible. Scanned documents are where POCs die — these
tiers exist to find that out in week 2, not week 4.
"""

from __future__ import annotations

import hashlib
import io
import random
import time
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

TIERS = ("clean", "scanned", "photographed")


def _seed_for(path: Path, tier: str) -> int:
    digest = hashlib.sha256(f"{path.name}:{tier}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _render_pages(pdf_path: Path, dpi: int) -> list[Image.Image]:
    doc = pdfium.PdfDocument(str(pdf_path))
    scale = dpi / 72
    pages = [page.render(scale=scale).to_pil() for page in doc]
    doc.close()
    return pages


def _add_noise(img: Image.Image, rng: random.Random, amount: float) -> Image.Image:
    # PIL's effect_noise is not seedable; generate noise from our own RNG so
    # degraded output is byte-for-byte reproducible.
    w, h = img.size
    noise = Image.frombytes("L", (w, h), rng.randbytes(w * h))
    noise = noise.convert(img.mode)
    return Image.blend(img, noise, 0.08 * amount)


def _scanned(page: Image.Image, rng: random.Random) -> Image.Image:
    img = page.convert("L")
    img = img.rotate(rng.uniform(-0.8, 0.8), expand=False,
                     fillcolor=245, resample=Image.BICUBIC)
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.82, 0.95))
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.94, 1.05))
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.4, 0.7)))
    img = _add_noise(img, rng, 0.35)
    return img


def _photographed(page: Image.Image, rng: random.Random) -> Image.Image:
    img = page.convert("RGB")
    img = img.rotate(rng.uniform(-2.5, 2.5), expand=True,
                     fillcolor=(212, 205, 194), resample=Image.BICUBIC)
    # Warm colour cast
    r, g, b = img.split()
    r = r.point(lambda v: min(255, int(v * 1.05)))
    b = b.point(lambda v: int(v * 0.93))
    img = Image.merge("RGB", (r, g, b))
    # Lighting gradient (shadow across the page)
    shade = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(shade)
    w, h = img.size
    x0 = rng.randint(-w // 2, w // 2)
    for x in range(w):
        val = int(70 * max(0, 1 - abs(x - x0 - w // 2) / (w * 0.9)))
        draw.line([(x, 0), (x, h)], fill=val)
    img = Image.composite(ImageEnhance.Brightness(img).enhance(0.72), img,
                          shade.filter(ImageFilter.GaussianBlur(60)))
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.6, 1.0)))
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.85, 0.95))
    img = _add_noise(img, rng, 0.3)
    return img


def degrade(pdf_in: Path, pdf_out: Path, tier: str) -> None:
    """Write a degraded copy of `pdf_in` at the given quality tier."""
    pdf_out.parent.mkdir(parents=True, exist_ok=True)
    if tier == "clean":
        pdf_out.write_bytes(pdf_in.read_bytes())
        return

    rng = random.Random(_seed_for(pdf_in, tier))
    dpi, jpeg_q = (200, 55) if tier == "scanned" else (150, 45)
    transform = _scanned if tier == "scanned" else _photographed

    out_pages = []
    for page in _render_pages(pdf_in, dpi):
        img = transform(page, rng)
        # Re-encode through JPEG to bake in compression artefacts
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=jpeg_q)
        out_pages.append(Image.open(buf).convert("RGB"))

    fixed_ts = time.gmtime(0)  # deterministic output: no wall-clock metadata
    out_pages[0].save(str(pdf_out), save_all=True, append_images=out_pages[1:],
                      format="PDF", resolution=dpi, title=pdf_in.stem,
                      creationDate=fixed_ts, modDate=fixed_ts)
