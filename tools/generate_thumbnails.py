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


# ---------------------------------------------------------------------------
# Luxury pack — generic metallic / gem renderers
# ---------------------------------------------------------------------------
def _metal(word, bgcol, stops, name, badge_text="LUXE", badge_col=(200, 170, 90),
           glow=None, size=64):
    img = bg(bgcol)
    mask, (x, y, tw, th) = text_mask(word, size, pad_top=-12)
    if glow:
        img = ImageChops.add(img, colorize(mask, glow).filter(ImageFilter.GaussianBlur(16)))
    grad = vgrad(stops)
    face = Image.new("RGB", (W, H), (0, 0, 0))
    face.paste(grad, (0, 0), mask)
    bv, hi_m, lo_m = bevel(mask, stops[-1][1], stops[0][1], depth=2)
    sh = colorize(mask, (0, 0, 0)).filter(ImageFilter.GaussianBlur(7))
    img = ImageChops.add(img, sh)
    img.paste(face, (0, 0), mask)
    img.paste(Image.new("RGB", (W, H), stops[-1][1]), (0, 0), hi_m)
    return finalize(badge(img, badge_text, badge_col), name)


def th_platinum():
    return _metal("PLATINUM", (16, 18, 22),
                  [(0.0, (90, 100, 116)), (0.34, (235, 240, 248)), (0.5, (150, 162, 180)),
                   (0.54, (220, 228, 240)), (0.78, (252, 254, 255)), (1.0, (96, 106, 122))],
                  "Platinum", badge_col=(150, 165, 185), size=52)


def th_rose_gold():
    return _metal("ROSE", (24, 16, 16),
                  [(0.0, (110, 60, 50)), (0.34, (255, 220, 206)), (0.5, (216, 150, 130)),
                   (0.54, (255, 226, 214)), (0.78, (255, 238, 230)), (1.0, (110, 60, 48))],
                  "Rose Gold", badge_col=(210, 150, 130), glow=(230, 160, 140))


def th_black_gold():
    img = bg((8, 8, 9))
    mask, _ = text_mask("BLACK", 60, pad_top=-12)
    gold = (230, 180, 80)
    img = ImageChops.add(img, colorize(mask, gold).filter(ImageFilter.GaussianBlur(16)))
    ring = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(5)), mask)
    img.paste((14, 14, 16), (0, 0), mask)
    img.paste(Image.new("RGB", (W, H), gold), (0, 0), ring)
    return finalize(badge(img, "LUXE", (210, 170, 90)), "Black & Gold")


def th_diamond():
    img = bg((12, 16, 22))
    mask, _ = text_mask("DIAMOND", 48, pad_top=-10)
    for r in (24, 12):
        img = ImageChops.add(img, colorize(mask, (180, 215, 255)).filter(ImageFilter.GaussianBlur(r)))
    grad = vgrad([(0.0, (150, 185, 220)), (0.4, (235, 245, 255)), (0.6, (200, 220, 245)), (1.0, (245, 252, 255))])
    face = Image.new("RGB", (W, H), (0, 0, 0)); face.paste(grad, (0, 0), mask)
    img.paste(face, (0, 0), mask)
    bv, hi_m, _ = bevel(mask, (255, 255, 255), (120, 150, 190), depth=2)
    img.paste(Image.new("RGB", (W, H), (255, 255, 255)), (0, 0), hi_m)
    return finalize(badge(img, "LUXE", (150, 200, 240)), "Diamond")


def th_champagne():
    return _metal("CHAMPAGNE", (22, 20, 14),
                  [(0.0, (120, 108, 70)), (0.36, (245, 235, 200)), (0.52, (210, 196, 150)),
                   (0.78, (255, 252, 240)), (1.0, (120, 108, 70))],
                  "Champagne", badge_col=(200, 188, 140), size=44)


def th_gem(word, name, bgcol, deep, mid, light, glow):
    img = bg(bgcol)
    mask, _ = text_mask(word, 60, pad_top=-12)
    img = ImageChops.add(img, colorize(mask, glow).filter(ImageFilter.GaussianBlur(18)))
    grad = vgrad([(0.0, deep), (0.45, mid), (0.5, light), (0.55, mid), (1.0, deep)])
    face = Image.new("RGB", (W, H), (0, 0, 0)); face.paste(grad, (0, 0), mask)
    img.paste(face, (0, 0), mask)
    bv, hi_m, _ = bevel(mask, light, deep, depth=2)
    img.paste(Image.new("RGB", (W, H), light), (0, 0), hi_m)
    return finalize(badge(img, "LUXE", glow), name)


def th_emerald():
    return th_gem("EMERALD", "Emerald Gem", (8, 18, 14), (6, 61, 41), (31, 181, 115), (196, 255, 226), (60, 200, 140))


def th_sapphire():
    return th_gem("SAPPHIRE", "Sapphire Gem", (8, 12, 24), (10, 30, 90), (43, 111, 224), (188, 216, 255), (90, 150, 240))


def th_royal_velvet():
    img = bg((20, 8, 14))
    mask, _ = text_mask("VELVET", 58, pad_top=-12)
    grad = vgrad([(0.0, (70, 16, 38)), (0.5, (140, 30, 70)), (1.0, (70, 16, 38))])
    face = Image.new("RGB", (W, H), (0, 0, 0)); face.paste(grad, (0, 0), mask)
    img.paste(face, (0, 0), mask)
    ring = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(3)), mask)
    img.paste(Image.new("RGB", (W, H), (201, 162, 75)), (0, 0), ring)
    return finalize(badge(img, "LUXE", (201, 162, 75)), "Royal Velvet")


def th_copper_bronze():
    return _metal("COPPER", (20, 12, 8),
                  [(0.0, (63, 32, 8)), (0.34, (255, 217, 160)), (0.5, (181, 116, 46)),
                   (0.54, (240, 190, 130)), (0.78, (255, 226, 180)), (1.0, (63, 32, 8))],
                  "Copper Bronze", badge_col=(200, 140, 70), glow=(210, 140, 70))


def th_marble_gold():
    import random
    img = bg((24, 24, 26))
    mask, _ = text_mask("MARBLE", 58, pad_top=-12)
    # white face
    img.paste(Image.new("RGB", (W, H), (242, 240, 234)), (0, 0), mask)
    # gold veins: random thin lines clipped to text
    veins = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(veins)
    random.seed(7)
    for _ in range(14):
        x0 = random.randint(0, W); y0 = random.randint(0, H)
        pts = [(x0, y0)]
        for _ in range(5):
            x0 += random.randint(-40, 40); y0 += random.randint(-30, 30)
            pts.append((x0, y0))
        d.line(pts, fill=255, width=1)
    veins = ImageChops.multiply(veins, mask)
    img.paste(Image.new("RGB", (W, H), (201, 162, 75)), (0, 0), veins)
    return finalize(badge(img, "LUXE", (201, 162, 75)), "Marble Gold")


# ---------------------------------------------------------------------------
# Luxury pack II
# ---------------------------------------------------------------------------
def th_ruby():
    return th_gem("RUBY", "Ruby Gem", (22, 8, 12), (74, 5, 17), (196, 30, 58), (255, 201, 210), (220, 80, 100))


def th_amethyst():
    return th_gem("AMETHYST", "Amethyst Gem", (16, 10, 24), (46, 17, 71), (155, 89, 208), (230, 204, 255), (170, 110, 230))


def th_onyx():
    img = bg((6, 6, 8))
    mask, _ = text_mask("ONYX", 66, pad_top=-12)
    grad = vgrad([(0.0, (10, 10, 12)), (0.35, (74, 74, 82)), (0.5, (20, 20, 24)),
                  (0.78, (54, 54, 62)), (1.0, (8, 8, 10))])
    face = Image.new("RGB", (W, H), (0, 0, 0)); face.paste(grad, (0, 0), mask)
    img.paste(face, (0, 0), mask)
    bv, hi_m, _ = bevel(mask, (160, 160, 172), (0, 0, 0), depth=2)
    img.paste(Image.new("RGB", (W, H), (130, 130, 142)), (0, 0), hi_m)
    return finalize(badge(img, "LUXE", (120, 120, 134)), "Onyx Gloss")


def th_pearl():
    return _metal("PEARL", (26, 24, 28),
                  [(0.0, (200, 188, 205)), (0.34, (255, 248, 240)), (0.5, (222, 208, 226)),
                   (0.78, (255, 252, 248)), (1.0, (198, 186, 205))],
                  "Pearl", badge_col=(210, 200, 215), size=58)


def th_titanium():
    return _metal("TITANIUM", (12, 13, 15),
                  [(0.0, (32, 36, 42)), (0.34, (150, 158, 168)), (0.5, (70, 76, 84)),
                   (0.78, (182, 190, 200)), (1.0, (30, 34, 40))],
                  "Titanium", badge_col=(140, 150, 162), size=46)


def th_liquid_gold():
    return _metal("GOLD", (20, 14, 4),
                  [(0.0, (106, 61, 2)), (0.3, (255, 232, 150)), (0.5, (196, 142, 36)),
                   (0.54, (255, 240, 170)), (0.78, (255, 250, 220)), (1.0, (106, 61, 2))],
                  "Liquid Gold", badge_col=(220, 170, 70), glow=(235, 175, 60), size=72)


def th_frosted_glass():
    img = bg((20, 26, 34))
    mask, _ = text_mask("GLASS", 70, pad_top=-12)
    tmp = img.copy()
    tmp.paste(Image.new("RGB", (W, H), (205, 222, 238)), (0, 0), mask)
    img = Image.blend(img, tmp, 0.62)
    bv, hi_m, _ = bevel(mask, (255, 255, 255), (120, 150, 180), depth=2)
    img.paste(Image.new("RGB", (W, H), (255, 255, 255)), (0, 0), hi_m)
    return finalize(badge(img, "LUXE", (170, 200, 225)), "Frosted Glass")


def th_holographic():
    import colorsys
    img = bg((16, 16, 22))
    mask, _ = text_mask("HOLO", 74, pad_top=-12)
    grad = Image.new("RGB", (W, H)); px = grad.load()
    for x in range(W):
        r, g, b = colorsys.hsv_to_rgb((x / W * 0.92) % 1.0, 0.55, 1.0)
        col = (int(r * 255), int(g * 255), int(b * 255))
        for y in range(H):
            px[x, y] = col
    face = Image.new("RGB", (W, H), (0, 0, 0)); face.paste(grad, (0, 0), mask)
    img = ImageChops.add(img, colorize(mask, (180, 180, 255)).filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.4)))
    img.paste(face, (0, 0), mask)
    return finalize(badge(img, "LUXE", (200, 120, 230)), "Holographic")


def th_neon_gold():
    img = bg((14, 11, 4), vignette=False)
    mask, _ = text_mask("GOLD", 78, pad_top=-12)
    gold = (255, 200, 80)
    for r in (26, 14, 6):
        img = ImageChops.add(img, colorize(mask, gold).filter(ImageFilter.GaussianBlur(r)))
    img.paste(Image.new("RGB", (W, H), (255, 242, 205)), (0, 0), mask)
    return finalize(badge(img, "LUXE", (220, 170, 70)), "Neon Gold")


def th_navy_gold():
    img = bg((6, 8, 16))
    mask, _ = text_mask("NAVY", 66, pad_top=-12)
    gold = (212, 169, 75)
    img = ImageChops.add(img, colorize(mask, gold).filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.55)))
    img.paste((22, 34, 72), (0, 0), mask)
    ring = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(5)), mask)
    img.paste(Image.new("RGB", (W, H), gold), (0, 0), ring)
    return finalize(badge(img, "LUXE", gold), "Navy & Gold")


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
    # luxury pack
    "platinum":     th_platinum,
    "rose_gold":    th_rose_gold,
    "black_gold":   th_black_gold,
    "diamond":      th_diamond,
    "champagne":    th_champagne,
    "emerald":      th_emerald,
    "sapphire":     th_sapphire,
    "royal_velvet": th_royal_velvet,
    "copper_bronze": th_copper_bronze,
    "marble_gold":  th_marble_gold,
    # luxury pack II
    "ruby":         th_ruby,
    "amethyst":     th_amethyst,
    "onyx":         th_onyx,
    "pearl":        th_pearl,
    "titanium":     th_titanium,
    "liquid_gold":  th_liquid_gold,
    "frosted_glass": th_frosted_glass,
    "holographic":  th_holographic,
    "neon_gold":    th_neon_gold,
    "navy_gold":    th_navy_gold,
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
