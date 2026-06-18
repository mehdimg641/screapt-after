#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thumbnail generator for Text Style Pro Max (After Effects panel).

Renders one preview PNG per text style so the ScriptUI panel can show a
real visual gallery. These previews are *approximations* of the look the
AE engine builds with layer styles + effects -- they exist so the editor
can browse styles at a glance before applying.

Run:  python3 tools/generate_thumbnails.py
Out:  assets/thumbnails/<id>.png   (one per style)
"""

import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "thumbnails")
OUT_DIR = os.path.abspath(OUT_DIR)
os.makedirs(OUT_DIR, exist_ok=True)

W, H = 360, 200          # thumbnail size (rendered @2x of panel display)
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


def load_font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def text_mask(word, size, canvas=(W, H), pad_top=0):
    """Return an L-mode mask (white text on black) centered in canvas."""
    font = load_font(size)
    m = Image.new("L", canvas, 0)
    d = ImageDraw.Draw(m)
    bbox = d.textbbox((0, 0), word, font=font, stroke_width=0)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (canvas[0] - tw) // 2 - bbox[0]
    y = (canvas[1] - th) // 2 - bbox[1] + pad_top
    d.text((x, y), word, font=font, fill=255)
    return m, (x, y, tw, th)


def vgrad(stops, size=(W, H)):
    """Vertical gradient. stops = list of (pos0..1, (r,g,b))."""
    w, h = size
    arr = np.zeros((h, w, 3), dtype=np.float32)
    ys = np.linspace(0, 1, h)
    cols = np.zeros((h, 3), dtype=np.float32)
    stops = sorted(stops, key=lambda s: s[0])
    for i in range(h):
        t = ys[i]
        for j in range(len(stops) - 1):
            p0, c0 = stops[j]
            p1, c1 = stops[j + 1]
            if p0 <= t <= p1:
                f = 0 if p1 == p0 else (t - p0) / (p1 - p0)
                cols[i] = np.array(c0) * (1 - f) + np.array(c1) * f
                break
        else:
            cols[i] = np.array(stops[-1][1] if t > stops[-1][0] else stops[0][1])
    arr[:] = cols[:, None, :]
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def bg(base=(22, 24, 30), vignette=True):
    img = Image.new("RGB", (W, H), base)
    if vignette:
        v = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(v)
        d.ellipse([-W * 0.3, -H * 0.4, W * 1.3, H * 1.4], fill=70)
        v = v.filter(ImageFilter.GaussianBlur(60))
        light = Image.new("RGB", (W, H), (255, 255, 255))
        img = Image.composite(
            Image.blend(img, light, 0.10), img, v)
    return img


def colorize(mask, color):
    solid = Image.new("RGB", mask.size, color)
    out = Image.new("RGB", mask.size, (0, 0, 0))
    out.paste(solid, (0, 0), mask)
    return out


def glow(mask, color, radius, gain=1.0):
    g = colorize(mask, color).filter(ImageFilter.GaussianBlur(radius))
    if gain != 1.0:
        g = ImageChops.multiply(g, Image.new("RGB", g.size,
              tuple(int(255 * gain) for _ in range(3)))) if gain < 1 else \
            ImageChops.add(g, g, scale=1.0 / gain)
    return g


def paste_masked(dst, src_rgb, mask):
    dst.paste(src_rgb, (0, 0), mask)
    return dst


def bevel(mask, hi=(255, 255, 255), lo=(0, 0, 0), depth=2, blur=1):
    """Cheap bevel: bright top-left edge, dark bottom-right edge."""
    edge = mask.filter(ImageFilter.GaussianBlur(blur))
    hi_m = ImageChops.subtract(edge, ImageChops.offset(edge, depth, depth))
    lo_m = ImageChops.subtract(edge, ImageChops.offset(edge, -depth, -depth))
    layer = Image.new("RGB", mask.size, (0, 0, 0))
    layer.paste(Image.new("RGB", mask.size, hi), (0, 0), hi_m)
    layer.paste(Image.new("RGB", mask.size, lo), (0, 0), lo_m)
    return layer, hi_m, lo_m


def badge(img, text, color=(255, 90, 90)):
    """Small trend badge in the top-right corner."""
    d = ImageDraw.Draw(img)
    f = load_font(15)
    tb = d.textbbox((0, 0), text, font=f)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    pad = 7
    x1, y1 = W - tw - pad * 2 - 10, 10
    x2, y2 = W - 10, y1 + th + pad * 2
    d.rounded_rectangle([x1, y1, x2, y2], radius=9, fill=color)
    d.text((x1 + pad, y1 + pad - tb[1]), text, font=f, fill=(255, 255, 255))
    return img


def finalize(img, name, sub=""):
    d = ImageDraw.Draw(img)
    f = load_font(16)
    d.text((14, H - 30), name, font=f, fill=(235, 238, 245))
    if sub:
        fs = load_font(12)
        tb = d.textbbox((0, 0), name, font=f)
        d.text((20 + tb[2], H - 28), sub, font=fs, fill=(140, 150, 165))
    # subtle border
    d.rectangle([0, 0, W - 1, H - 1], outline=(60, 66, 78))
    return img


# ---------------------------------------------------------------------------
# Individual style renderers
# ---------------------------------------------------------------------------
def th_chrome():
    img = bg((18, 20, 26))
    mask, _ = text_mask("CHROME", 70, pad_top=-12)
    grad = vgrad([(0.0, (60, 70, 90)), (0.34, (235, 240, 250)),
                  (0.5, (120, 135, 160)), (0.52, (200, 215, 235)),
                  (0.75, (250, 252, 255)), (1.0, (70, 80, 100))])
    face = Image.new("RGB", (W, H), (0, 0, 0))
    face.paste(grad, (0, 0), mask)
    bv, hi_m, lo_m = bevel(mask, (255, 255, 255), (20, 28, 45), depth=2, blur=1)
    sh = colorize(mask, (0, 0, 0)).filter(ImageFilter.GaussianBlur(6))
    img = Image.blend(img, ImageChops.add(img, sh), 0.5)
    img.paste(face, (0, 0), mask)
    img = ImageChops.add(img, ImageChops.multiply(bv, Image.new("RGB", (W, H), (255, 255, 255))), scale=1.0)
    img.paste(Image.new("RGB", (W, H), (255, 255, 255)), (0, 0), hi_m.point(lambda v: int(v * 0.9)))
    return finalize(badge(img, "NEW"), "Chrome Y2K")


def th_gold():
    img = bg((20, 16, 10))
    mask, _ = text_mask("ROYAL", 72, pad_top=-12)
    grad = vgrad([(0.0, (120, 80, 20)), (0.32, (255, 226, 140)),
                  (0.5, (180, 130, 45)), (0.54, (255, 236, 170)),
                  (0.78, (255, 248, 205)), (1.0, (110, 70, 18))])
    face = Image.new("RGB", (W, H), (0, 0, 0))
    face.paste(grad, (0, 0), mask)
    bv, hi_m, lo_m = bevel(mask, (255, 248, 210), (90, 55, 12), depth=2)
    sh = colorize(mask, (0, 0, 0)).filter(ImageFilter.GaussianBlur(7))
    img = ImageChops.add(img, sh)
    gl = colorize(mask, (255, 200, 90)).filter(ImageFilter.GaussianBlur(14))
    img = ImageChops.add(img, gl.point(lambda v: int(v * 0.5)))
    img.paste(face, (0, 0), mask)
    img.paste(Image.new("RGB", (W, H), (255, 250, 220)), (0, 0), hi_m)
    return finalize(badge(img, "HOT", (255, 140, 40)), "Gold Luxury")


def th_kinetic():
    img = bg((24, 26, 34))
    # ghosted trailing copies to suggest motion
    for i, a in enumerate([0.12, 0.22, 0.4]):
        off = (i + 1) * 12
        m, _ = text_mask("KINETIC", 52, pad_top=-10)
        m = ImageChops.offset(m, -off, 0)
        ghost = colorize(m, (90, 170, 255))
        img = Image.blend(img, ImageChops.add(img, ghost), a)
    m, _ = text_mask("KINETIC", 52, pad_top=-10)
    img.paste(Image.new("RGB", (W, H), (245, 248, 255)), (0, 0), m)
    d = ImageDraw.Draw(img)
    d.line([40, H - 52, W - 40, H - 52], fill=(90, 170, 255), width=3)
    return finalize(badge(img, "AE 2026", (90, 130, 255)), "Variable Kinetic")


def th_neon():
    img = bg((10, 10, 16), vignette=False)
    mask, _ = text_mask("NEON", 76, pad_top=-12)
    cyan = (24, 224, 255)
    for r, g in [(26, 1.0), (14, 1.0), (6, 1.0)]:
        img = ImageChops.add(img, colorize(mask, cyan).filter(ImageFilter.GaussianBlur(r)))
    img.paste(Image.new("RGB", (W, H), (220, 252, 255)), (0, 0),
              mask.filter(ImageFilter.GaussianBlur(0.6)))
    # thin core
    core = mask.point(lambda v: 255 if v > 180 else 0)
    img.paste(Image.new("RGB", (W, H), (255, 255, 255)), (0, 0), core)
    return finalize(badge(img, "HOT", (255, 60, 140)), "Neon Cyberpunk")


def th_marquee():
    img = bg((26, 18, 34))
    mask, (x, y, tw, th) = text_mask("CLUB", 78, pad_top=-12)
    purple = (170, 70, 240)
    img = ImageChops.add(img, colorize(mask, purple).filter(ImageFilter.GaussianBlur(20)))
    face = colorize(mask, (150, 60, 220))
    img.paste(face, (0, 0), mask)
    # bulb ring
    ring = ImageChops.subtract(mask, ImageChops.offset(mask.filter(ImageFilter.MaxFilter(7)), 0, 0))
    img.paste(Image.new("RGB", (W, H), (245, 220, 255)), (0, 0),
              ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(5)), mask))
    # decorative bulbs
    d = ImageDraw.Draw(img)
    for bx in range(x, x + tw, 26):
        for by in (y - 6, y + th + 2):
            d.ellipse([bx, by, bx + 7, by + 7], fill=(255, 240, 200))
    return finalize(badge(img, "RETRO", (200, 120, 60)), "Retro Marquee")


def th_3d():
    img = bg((205, 150, 95), vignette=True)  # warm seamless-paper vibe
    word = "3D"
    steps = 16
    base, _ = text_mask("EXTRUDE", 56, pad_top=-8)
    # extrude: stack darker offset copies down-right
    for i in range(steps, 0, -1):
        shade = int(60 + (steps - i) * 5)
        m = ImageChops.offset(base, int(i * 2.2), int(i * 2.2))
        img.paste((shade, shade // 2 + 20, shade // 3), (0, 0), m)
    grad = vgrad([(0.0, (255, 235, 200)), (1.0, (210, 160, 110))])
    face = Image.new("RGB", (W, H), (0, 0, 0))
    face.paste(grad, (0, 0), base)
    img.paste(face, (0, 0), base)
    return finalize(badge(img, "3D", (120, 90, 60)), "3D Extrude")


def th_glitch():
    img = bg((12, 12, 16), vignette=False)
    mask, _ = text_mask("GLITCH", 66, pad_top=-12)
    r = colorize(ImageChops.offset(mask, -6, 2), (255, 40, 70))
    b = colorize(ImageChops.offset(mask, 6, -2), (40, 180, 255))
    img = ImageChops.add(img, r)
    img = ImageChops.add(img, b)
    img.paste(Image.new("RGB", (W, H), (235, 235, 235)), (0, 0), mask)
    # scanline slices
    arr = np.array(img)
    for yb in range(20, H, 9):
        arr[yb:yb + 1] = (arr[yb:yb + 1] * 0.5).astype(np.uint8)
    img = Image.fromarray(arr)
    return finalize(badge(img, "FX", (90, 200, 120)), "Glitch VHS")


def th_fluid():
    img = bg((14, 18, 30))
    mask, _ = text_mask("FLUID", 74, pad_top=-12)
    # wobble the mask with a sine displacement for liquid edges
    arr = np.array(mask)
    out = np.zeros_like(arr)
    for yy in range(H):
        dx = int(6 * math.sin(yy / 11.0))
        out[yy] = np.roll(arr[yy], dx)
    wob = Image.fromarray(out)
    grad = vgrad([(0.0, (80, 130, 255)), (1.0, (190, 80, 255))])
    face = Image.new("RGB", (W, H), (0, 0, 0))
    face.paste(grad, (0, 0), wob)
    img = ImageChops.add(img, colorize(wob, (120, 90, 255)).filter(ImageFilter.GaussianBlur(16)))
    img.paste(face, (0, 0), wob)
    img.paste(Image.new("RGB", (W, H), (255, 255, 255)), (0, 0),
              ImageChops.subtract(wob, ImageChops.offset(wob, 2, 3)).point(lambda v: int(v * 0.7)))
    return finalize(badge(img, "TREND", (120, 90, 255)), "Fluid Morph")


def th_gradient():
    img = bg((18, 18, 24))
    mask, _ = text_mask("GRADIENT", 50, pad_top=-10)
    # diagonal 2-color gradient (insta vibe)
    w, h = W, H
    xx, yy = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, h))
    t = (xx + yy) / 2
    c0 = np.array([255, 70, 150]); c1 = np.array([120, 90, 255])
    g = (c0[None, None] * (1 - t[..., None]) + c1[None, None] * t[..., None]).astype(np.uint8)
    grad = Image.fromarray(g, "RGB")
    face = Image.new("RGB", (W, H), (0, 0, 0))
    face.paste(grad, (0, 0), mask)
    sh = colorize(mask, (0, 0, 0)).filter(ImageFilter.GaussianBlur(5))
    img = ImageChops.add(img, sh)
    img.paste(face, (0, 0), mask)
    return finalize(badge(img, "SOCIAL", (90, 170, 255)), "Gradient Bold")


def th_outline():
    img = bg((20, 22, 28))
    mask, _ = text_mask("OUTLINE", 56, pad_top=-10)
    thick = mask.filter(ImageFilter.MaxFilter(7))
    ring = ImageChops.subtract(thick, mask)
    # soft sticker shadow
    sh = thick.filter(ImageFilter.GaussianBlur(5))
    img = ImageChops.add(img, ImageChops.offset(colorize(sh, (0, 0, 0)), 3, 5))
    img.paste(Image.new("RGB", (W, H), (255, 110, 180)), (0, 0), ring)
    return finalize(badge(img, "Y2K", (255, 110, 180)), "Outline Bubble")


RENDERERS = {
    "chrome_y2k":   th_chrome,
    "gold_luxury":  th_gold,
    "variable_kinetic": th_kinetic,
    "neon_cyberpunk":   th_neon,
    "retro_marquee":    th_marquee,
    "extrude_3d":   th_3d,
    "glitch_vhs":   th_glitch,
    "fluid_morph":  th_fluid,
    "gradient_bold": th_gradient,
    "outline_bubble": th_outline,
}


def main():
    for sid, fn in RENDERERS.items():
        img = fn().convert("RGB")
        path = os.path.join(OUT_DIR, sid + ".png")
        img.save(path, "PNG")
        print("wrote", os.path.relpath(path))
    print("done:", len(RENDERERS), "thumbnails ->", OUT_DIR)


if __name__ == "__main__":
    main()
