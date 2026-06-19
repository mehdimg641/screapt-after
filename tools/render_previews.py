#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Faithful preview RENDERER for Text Style Pro Max.

Unlike the small gallery thumbnails, this simulates the actual AE effect stack
each style applies (text fill + Bevel Alpha + stroke + Glow + Drop Shadow, etc.)
so we can judge the real look without opening After Effects.

It is an approximation, but it mirrors the same colours / parameters as the
recipes in TextStyleProMax.jsx.

Run:  python3 tools/render_previews.py
Out:  /tmp/render/<id>.png  and grouped contact sheets.
"""
import os, math, random, colorsys, io
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

W, H = 560, 300
OUT = "/tmp/render"
os.makedirs(OUT, exist_ok=True)

FONTS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def font(sz):
    for p in FONTS:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def hx(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def mask_of(word, size):
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    f = font(size)
    bb = d.textbbox((0, 0), word, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x = (W - tw) // 2 - bb[0]
    y = (H - th) // 2 - bb[1] - 14
    d.text((x, y), word, font=f, fill=255)
    return m, (x, y, tw, th)


def fit_size(word, target_w=440, start=150):
    f = font(start)
    d = ImageDraw.Draw(Image.new("L", (10, 10)))
    bb = d.textbbox((0, 0), word, font=f)
    w = bb[2] - bb[0]
    return max(40, int(start * target_w / max(1, w)))


def bg(color=(18, 19, 23), vignette=True):
    img = Image.new("RGB", (W, H), color)
    if vignette:
        v = Image.new("L", (W, H), 0)
        ImageDraw.Draw(v).ellipse([-W * .3, -H * .4, W * 1.3, H * 1.4], fill=60)
        v = v.filter(ImageFilter.GaussianBlur(90))
        img = Image.composite(Image.blend(img, Image.new("RGB", (W, H), (255, 255, 255)), .08), img, v)
    return img


def fill_rgb(mask, color):
    o = Image.new("RGB", (W, H), (0, 0, 0))
    o.paste(Image.new("RGB", (W, H), color), (0, 0), mask)
    return o


def paste(dst, color, mask):
    dst.paste(Image.new("RGB", (W, H), color), (0, 0), mask)


def sheen(face_rgb, mask, top_gain=1.28, bot_gain=0.72, band=True):
    """Vertical metallic sheen + a bright horizontal highlight band."""
    arr = np.asarray(face_rgb).astype(np.float32)
    ys = np.linspace(top_gain, bot_gain, H)[:, None, None]
    arr *= ys
    if band:
        yy = np.arange(H)[:, None, None]
        center = H * 0.40
        b = np.exp(-((yy - center) ** 2) / (2 * (H * 0.07) ** 2)) * 90
        arr += b
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    out = Image.fromarray(arr)
    res = Image.new("RGB", (W, H), (0, 0, 0))
    res.paste(out, (0, 0), mask)
    return res


def emboss(face, mask, light_deg, hi_color, strength=1.0, thick=3, shadow_color=(0, 0, 0)):
    a = math.radians(light_deg)
    dx, dy = int(round(math.cos(a) * thick)), int(round(-math.sin(a) * thick))
    blur = mask.filter(ImageFilter.GaussianBlur(1))
    hi = ImageChops.subtract(blur, ImageChops.offset(blur, -dx, -dy))
    lo = ImageChops.subtract(blur, ImageChops.offset(blur, dx, dy))
    hi = hi.point(lambda v: int(min(255, v * strength)))
    lo = lo.point(lambda v: int(min(255, v * strength)))
    out = face.copy()
    out.paste(Image.new("RGB", (W, H), hi_color), (0, 0), hi)
    out.paste(Image.new("RGB", (W, H), shadow_color), (0, 0), lo.point(lambda v: int(v * 0.7)))
    return out


def glow_layer(mask, color, radius, gain=1.0, passes=2):
    base = fill_rgb(mask, color)
    acc = Image.new("RGB", (W, H), (0, 0, 0))
    r = radius
    for _ in range(passes):
        acc = ImageChops.add(acc, base.filter(ImageFilter.GaussianBlur(r)))
        r = max(2, int(r * 0.5))
    if gain != 1.0:
        acc = acc.point(lambda v: int(min(255, v * gain)))
    return acc


def ring(mask, width):
    return ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(width * 2 + 1)), mask)


def spec_streak(img, mask, color=(255, 255, 255), x=0.34, w=72, alpha=0.6):
    """A diagonal specular shine clipped to the letters (mirrors CC Light Sweep)."""
    streak = Image.new("L", (W, H), 0)
    cx = int(W * x)
    ImageDraw.Draw(streak).polygon([(cx, 0), (cx + w, 0), (cx - 50, H), (cx - 120, H)], fill=int(255 * alpha))
    streak = ImageChops.multiply(streak.filter(ImageFilter.GaussianBlur(13)), mask)
    img.paste(Image.new("RGB", (W, H), color), (0, 0), streak)
    return img


def label(img, name):
    d = ImageDraw.Draw(img)
    d.text((16, H - 30), name, font=font(20), fill=(235, 238, 245))
    d.rectangle([0, 0, W - 1, H - 1], outline=(58, 62, 74))
    return img


# ---------------------------------------------------------------------------
# Generic renderers
# ---------------------------------------------------------------------------
def render_metal(word, fill, bevel_hi, stroke, glow=None, glow_r=22, warm=False,
                 bgc=(18, 19, 23), band=True, sheen_amt=(1.30, 0.70)):
    img = bg(bgc)
    sz = fit_size(word)
    m, _ = mask_of(word, sz)
    # drop shadow
    sh = fill_rgb(m, (0, 0, 0)).filter(ImageFilter.GaussianBlur(12))
    img = ImageChops.subtract(img, ImageChops.offset(sh, 6, 9).point(lambda v: int(v * 0.5)))
    # glow
    if glow:
        img = ImageChops.add(img, glow_layer(m, glow, glow_r, 0.7))
    # face
    face = sheen(fill_rgb(m, fill), m, sheen_amt[0], sheen_amt[1], band)
    face = emboss(face, m, 122, bevel_hi, 1.0, 3,
                  shadow_color=tuple(int(c * 0.35) for c in fill))
    img.paste(face, (0, 0), m)
    # stroke
    if stroke:
        paste(img, stroke, ring(m, 2))
    # specular shine
    img = spec_streak(img, m, alpha=0.5)
    return img


def render_gem(word, fill, edge, glow, glow_r=30, bgc=(12, 12, 18)):
    img = bg(bgc)
    sz = fit_size(word)
    m, _ = mask_of(word, sz)
    img = ImageChops.add(img, glow_layer(m, glow, glow_r, 1.1, passes=3))
    face = sheen(fill_rgb(m, fill), m, 1.45, 0.6)
    face = emboss(face, m, 122, edge, 1.3, 4, shadow_color=tuple(int(c * .3) for c in fill))
    img.paste(face, (0, 0), m)
    paste(img, edge, ring(m, 2))
    # facet sparkle
    paste(img, (255, 255, 255), ring(m, 1).point(lambda v: v if random.random() > .3 else 0))
    # specular shine
    img = spec_streak(img, m, alpha=0.65)
    return img


# ---------------------------------------------------------------------------
# Per-style table  (mirrors TextStyleProMax.jsx recipes)
# ---------------------------------------------------------------------------
def r_chrome():   return render_metal("CHROME", hx("#D9DEE8"), (255, 255, 255), hx("#5A6573"), bgc=(14, 16, 22))
def r_gold():     return render_metal("ROYAL", hx("#E6B450"), hx("#FFF4C8"), hx("#7A521A"), glow=hx("#FFCB5E"), glow_r=26, warm=True, bgc=(20, 16, 8))
def r_platinum(): return render_metal("PLATINUM", hx("#DCE2EA"), (255, 255, 255), hx("#6E7888"), bgc=(15, 16, 20))
def r_rose():     return render_metal("ROSE GOLD", hx("#E8B4A0"), hx("#FFE8DE"), hx("#8A4A3A"), glow=hx("#E0A38E"), glow_r=20, warm=True, bgc=(22, 15, 14))
def r_champagne():return render_metal("CHAMPAGNE", hx("#EFE2BE"), hx("#FFFDF2"), hx("#A8965E"), warm=True, bgc=(20, 18, 12))
def r_copper():   return render_metal("COPPER", hx("#B5742E"), hx("#FFD9A0"), hx("#5E3A12"), glow=hx("#E2965A"), glow_r=22, warm=True, bgc=(20, 12, 8))
def r_titanium(): return render_metal("TITANIUM", hx("#5A6068"), hx("#C4CAD2"), hx("#2A2E34"), bgc=(12, 13, 15))
def r_liquidgold():return render_metal("GOLD", hx("#F0C04A"), hx("#FFFBE0"), hx("#7A5212"), glow=hx("#FFD060"), glow_r=40, warm=True, bgc=(18, 13, 4))
def r_pearl():    return render_metal("PEARL", hx("#F4EEE6"), (255, 255, 255), hx("#C8B8D6"), glow=hx("#EAD9F0"), glow_r=18, bgc=(22, 20, 24), sheen_amt=(1.18, 0.86))

def r_diamond():  return render_gem("DIAMOND", hx("#DCEBFF"), (255, 255, 255), hx("#BFE0FF"), 42, bgc=(12, 16, 24))
def r_emerald():  return render_gem("EMERALD", hx("#1FB573"), hx("#CFFFE6"), hx("#3CE0A0"), 30, bgc=(8, 18, 14))
def r_sapphire(): return render_gem("SAPPHIRE", hx("#2B6FE0"), hx("#CFE2FF"), hx("#5A96F0"), 30, bgc=(8, 12, 26))
def r_ruby():     return render_gem("RUBY", hx("#C41E3A"), hx("#FFD0D8"), hx("#E85070"), 30, bgc=(22, 8, 12))
def r_amethyst(): return render_gem("AMETHYST", hx("#9B59D0"), hx("#EEDBFF"), hx("#BE82E6"), 30, bgc=(16, 10, 24))


def r_black_gold():
    img = bg((8, 8, 9))
    m, _ = mask_of("BLACK GOLD", fit_size("BLACK GOLD"))
    img = ImageChops.add(img, glow_layer(m, hx("#E6B450"), 24, 0.8))
    face = emboss(fill_rgb(m, (13, 13, 15)), m, 122, hx("#FFE6A0"), 0.7, 2)
    img.paste(face, (0, 0), m)
    paste(img, hx("#E6B450"), ring(m, 3))
    return img


def r_royal_velvet():
    img = bg((20, 8, 14))
    m, _ = mask_of("VELVET", fit_size("VELVET"))
    face = sheen(fill_rgb(m, hx("#6E1230")), m, 1.18, 0.7, band=False)
    face = emboss(face, m, 120, hx("#9E2A52"), 0.5, 2)
    img.paste(face, (0, 0), m)
    paste(img, hx("#C9A24B"), ring(m, 2))
    img = ImageChops.add(img, glow_layer(m, hx("#7A1838"), 16, 0.4))
    return img


def render_onyx(word, base_dark, sheen_col, ring_col, glow_col=None, bgc=(6, 6, 8)):
    img = bg(bgc)
    m, _ = mask_of(word, fit_size(word))
    if glow_col:
        img = ImageChops.add(img, glow_layer(m, glow_col, 16, 0.4))
    face = sheen(fill_rgb(m, base_dark), m, 2.1, 0.45, band=True)
    face = emboss(face, m, 122, sheen_col, 1.15, 3, shadow_color=(0, 0, 0))
    img.paste(face, (0, 0), m)
    paste(img, ring_col, ring(m, 2))
    img = spec_streak(img, m, alpha=0.7)
    return img


def r_onyx_classic():
    # the original recipe: glossy black, white steel sheen, no specular sweep
    img = bg((6, 6, 8))
    m, _ = mask_of("ONYX", fit_size("ONYX"))
    face = sheen(fill_rgb(m, (12, 12, 14)), m, 1.9, 0.5)
    face = emboss(face, m, 122, (200, 200, 210), 0.9, 3)
    img.paste(face, (0, 0), m)
    paste(img, hx("#26262C"), ring(m, 2))
    return img


def _shade(c, f):
    if f >= 0:
        return tuple(int(c[i] + (255 - c[i]) * f) for i in range(3))
    return tuple(int(c[i] * (1 + f)) for i in range(3))


def render_onyx_accent(word, accent_hex):
    """Same logic as the JSX onyxSurface(accent) so render == AE."""
    a = hx(accent_hex)
    base_dark = _shade(a, -0.80)
    sheen = _shade(a, 0.45)
    ring_c = _shade(a, -0.4)
    bgc = tuple(int(x * 0.4) for x in base_dark)
    return render_onyx(word, base_dark, sheen, ring_c, a, bgc)


def r_onyx():          return render_onyx("ONYX", (14, 14, 16), (205, 205, 214), hx("#26262C"))
def r_teal_aqua():      return render_onyx_accent("AQUA", "#1FD0C0")
def r_teal_turquoise(): return render_onyx_accent("TURQUOISE", "#1AB6A0")
def r_teal_cyan():      return render_onyx_accent("CYAN", "#18C8E8")
def r_teal_mint():      return render_onyx_accent("MINT", "#58E0A8")
def r_teal_lagoon():    return render_onyx_accent("LAGOON", "#1E9FB8")
def r_teal_seafoam():   return render_onyx_accent("SEAFOAM", "#84E0C8")
def r_teal_petrol():    return render_onyx_accent("PETROL", "#0E8A92")
def r_teal_tiffany():   return render_onyx_accent("TIFFANY", "#2EC4C0")
def r_teal_spearmint(): return render_onyx_accent("SPEARMINT", "#34D094")
def r_teal_ice():       return render_onyx_accent("ICE", "#6FE8E8")
def r_onyx_sapphire(): return render_onyx("SAPPHIRE", (8, 16, 34), (110, 160, 235), hx("#1E3257"), (50, 100, 210), (5, 8, 18))
def r_onyx_emerald():  return render_onyx("EMERALD", (6, 22, 15), (95, 224, 160), hx("#16402C"), (30, 170, 110), (4, 14, 9))
def r_onyx_ruby():     return render_onyx("RUBY", (28, 8, 12), (255, 120, 140), hx("#551823"), (210, 55, 85), (16, 4, 7))
def r_onyx_amethyst(): return render_onyx("AMETHYST", (20, 12, 34), (190, 140, 240), hx("#3C2857"), (150, 90, 230), (12, 7, 20))
def r_onyx_gold():     return render_onyx("GOLD", (26, 18, 6), (255, 222, 140), hx("#5A4218"), (220, 160, 55), (16, 11, 4))
def r_onyx_teal():     return render_onyx("TEAL", (4, 26, 28), (95, 224, 224), hx("#164648"), (35, 175, 180), (3, 15, 16))


def r_navy_gold():
    img = bg((6, 8, 16))
    m, _ = mask_of("NAVY GOLD", fit_size("NAVY GOLD"))
    img = ImageChops.add(img, glow_layer(m, hx("#D4A94B"), 20, 0.5))
    face = emboss(fill_rgb(m, hx("#16244A")), m, 122, hx("#FFE6A0"), 0.6, 2)
    img.paste(face, (0, 0), m)
    paste(img, hx("#D4A94B"), ring(m, 3))
    return img


def r_neon():
    img = bg((10, 10, 16), vignette=False)
    m, _ = mask_of("NEON", fit_size("NEON"))
    neon = hx("#18E0FF")
    for r, g in [(34, 1.0), (18, 1.0), (8, 1.0)]:
        img = ImageChops.add(img, glow_layer(m, neon, r, g, passes=1))
    paste(img, (220, 252, 255), m.filter(ImageFilter.GaussianBlur(0.6)))
    paste(img, (255, 255, 255), m.point(lambda v: 255 if v > 180 else 0))
    paste(img, neon, ring(m, 2))
    return img


def r_neon_gold():
    img = bg((14, 11, 4), vignette=False)
    m, _ = mask_of("GOLD", fit_size("GOLD"))
    gold = hx("#FFB02E")
    for r in (34, 18, 8):
        img = ImageChops.add(img, glow_layer(m, gold, r, 1.0, passes=1))
    paste(img, hx("#FFE6A8"), m)
    paste(img, gold, ring(m, 2))
    return img


def r_marquee():
    img = bg((26, 18, 34))
    m, (x, y, tw, th) = mask_of("CLUB", fit_size("CLUB"))
    c = hx("#A646F0")
    img = ImageChops.add(img, glow_layer(m, c, 26, 0.8))
    face = emboss(fill_rgb(m, c), m, 120, (255, 255, 255), 0.9, 4)
    img.paste(face, (0, 0), m)
    paste(img, hx("#E0B8FF"), ring(m, 3))
    d = ImageDraw.Draw(img)
    for bx in range(x, x + tw, 40):
        for by in (y - 10, y + th + 4):
            d.ellipse([bx, by, bx + 10, by + 10], fill=(255, 240, 200))
    return img


def r_outline():
    img = bg((22, 16, 26))
    m, _ = mask_of("BUBBLE", fit_size("BUBBLE"))
    c = hx("#FF6EB4")
    sh = fill_rgb(m, (0, 0, 0)).filter(ImageFilter.GaussianBlur(12))
    img = ImageChops.subtract(img, ImageChops.offset(sh, 8, 12).point(lambda v: int(v * 0.5)))
    face = sheen(fill_rgb(m, c), m, 1.35, 0.72, band=True)
    face = emboss(face, m, 122, (255, 232, 246), 1.2, 5, shadow_color=tuple(int(x * 0.4) for x in c))
    img.paste(face, (0, 0), m)
    paste(img, tuple(int(x * 0.5) for x in c), ring(m, 5))
    img = spec_streak(img, m, alpha=0.7)
    return img


def r_3d():
    img = bg((205, 150, 95))
    word = "EXTRUDE"
    base, _ = mask_of(word, fit_size(word, 430))
    face_c = hx("#E9C39A"); side = hx("#7C5A36")
    for i in range(16, 0, -1):
        f = i / 16
        col = tuple(int(side[k] * (0.7 + 0.3 * f)) for k in range(3))
        img.paste(col, (0, 0), ImageChops.offset(base, int(i * 2.4), int(i * 2.4)))
    face = emboss(sheen(fill_rgb(base, face_c), base, 1.2, 0.85), base, 122, (255, 245, 225), 0.6, 2)
    img.paste(face, (0, 0), base)
    return img


def r_glitch():
    img = bg((12, 12, 16), vignette=False)
    m, _ = mask_of("GLITCH", fit_size("GLITCH"))
    img = ImageChops.add(img, fill_rgb(ImageChops.offset(m, -8, 2), (255, 40, 70)))
    img = ImageChops.add(img, fill_rgb(ImageChops.offset(m, 8, -2), (40, 180, 255)))
    paste(img, (236, 236, 238), m)
    arr = np.array(img)
    for yb in range(24, H, 12):
        arr[yb:yb + 2] = (arr[yb:yb + 2] * 0.45).astype(np.uint8)
    return Image.fromarray(arr)


def r_fluid():
    img = bg((14, 18, 30))
    m, _ = mask_of("FLUID", fit_size("FLUID"))
    arr = np.array(m); out = np.zeros_like(arr)
    for yy in range(H):
        out[yy] = np.roll(arr[yy], int(9 * math.sin(yy / 13.0)))
    wob = Image.fromarray(out)
    a, b = hx("#5B8CFF"), hx("#B852FF")
    img = ImageChops.add(img, glow_layer(wob, b, 24, 0.7))
    # 2-colour vertical gradient body
    ys = np.linspace(0, 1, H)[:, None, None]
    grad = (np.array(b) * (1 - ys) + np.array(a) * ys) * np.ones((H, W, 1))
    body = Image.new("RGB", (W, H), (0, 0, 0))
    body.paste(Image.fromarray(grad.astype(np.uint8)), (0, 0), wob)
    img.paste(body, (0, 0), wob)
    emb = emboss(img.copy(), wob, 122, hx("#E0CCFF"), 1.1, 3, shadow_color=(30, 30, 70))
    img.paste(emb, (0, 0), wob)
    img = spec_streak(img, wob, alpha=0.6)
    return img


def r_gradient_bold():
    img = bg((18, 18, 24))
    m, _ = mask_of("GRADIENT", fit_size("GRADIENT", 470))
    xx, yy = np.meshgrid(np.linspace(0, 1, W), np.linspace(0, 1, H))
    t = (xx + yy) / 2
    a, b = np.array(hx("#FF4696")), np.array(hx("#785AFF"))
    g = (a[None, None] * (1 - t[..., None]) + b[None, None] * t[..., None]).astype(np.uint8)
    face = Image.new("RGB", (W, H), (0, 0, 0)); face.paste(Image.fromarray(g), (0, 0), m)
    sh = fill_rgb(m, (0, 0, 0)).filter(ImageFilter.GaussianBlur(8))
    img = ImageChops.subtract(img, ImageChops.offset(sh, 5, 8).point(lambda v: int(v * .5)))
    img.paste(face, (0, 0), m)
    return img


def r_holographic():
    img = bg((16, 16, 22))
    m, _ = mask_of("HOLO", fit_size("HOLO"))
    grad = Image.new("RGB", (W, H)); px = grad.load()
    for xp in range(W):
        rr, gg, bb = colorsys.hsv_to_rgb((xp / W * 0.92) % 1.0, 0.55, 1.0)
        for yp in range(H):
            px[xp, yp] = (int(rr * 255), int(gg * 255), int(bb * 255))
    face = Image.new("RGB", (W, H), (0, 0, 0)); face.paste(grad, (0, 0), m)
    face = emboss(face, m, 122, (255, 255, 255), 0.6, 2)
    img = ImageChops.add(img, glow_layer(m, (180, 180, 255), 18, 0.4))
    img.paste(face, (0, 0), m)
    return img


def r_marble():
    img = bg((24, 24, 26))
    m, _ = mask_of("MARBLE", fit_size("MARBLE"))
    paste(img, (242, 240, 234), m)
    veins = Image.new("L", (W, H), 0); d = ImageDraw.Draw(veins)
    random.seed(7)
    for _ in range(18):
        x0, y0 = random.randint(0, W), random.randint(0, H); pts = [(x0, y0)]
        for _ in range(6):
            x0 += random.randint(-60, 60); y0 += random.randint(-40, 40); pts.append((x0, y0))
        d.line(pts, fill=255, width=2)
    veins = ImageChops.multiply(veins, m)
    paste(img, hx("#C9A24B"), veins)
    img2 = emboss(img, m, 122, (255, 255, 255), 0.4, 2)
    img2.paste(img2, (0, 0), m)
    return img2


def r_frosted():
    # textured background so the glass translucency + refraction actually reads
    bgimg = bg((24, 32, 46))
    d = ImageDraw.Draw(bgimg)
    for (cx, cy, r, col) in [(150, 90, 130, (70, 110, 160)), (430, 210, 150, (110, 80, 150)), (300, 60, 110, (60, 140, 170))]:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    bgimg = bgimg.filter(ImageFilter.GaussianBlur(45))
    m, _ = mask_of("GLASS", fit_size("GLASS"))
    img = bgimg.copy()
    # drop shadow
    sh = fill_rgb(m, (0, 0, 0)).filter(ImageFilter.GaussianBlur(14))
    img = ImageChops.subtract(img, ImageChops.offset(sh, 8, 12).point(lambda v: int(v * 0.45)))
    # glass body = refracted background + a light vertical gradient (clear, not faded)
    refr = ImageChops.offset(bgimg, 7, -7)
    arr = np.asarray(refr).astype(np.float32)
    ys = np.linspace(1.35, 0.72, H)[:, None, None]
    glass = np.clip(arr * 0.42 + np.array([205, 228, 248]) * 0.58 * ys, 0, 255).astype(np.uint8)
    body = img.copy(); body.paste(Image.fromarray(glass), (0, 0), m)
    img = Image.blend(img, body, 0.9)  # translucent
    # bright refractive bevel edges
    emb = emboss(img.copy(), m, 122, (255, 255, 255), 1.5, 4, shadow_color=(20, 40, 60))
    img.paste(emb, (0, 0), m)
    # diagonal specular streak (clipped to the letters)
    streak = Image.new("L", (W, H), 0)
    ImageDraw.Draw(streak).polygon([(150, 0), (250, 0), (140, H), (40, H)], fill=130)
    streak = ImageChops.multiply(streak.filter(ImageFilter.GaussianBlur(16)), m)
    img.paste(Image.new("RGB", (W, H), (255, 255, 255)), (0, 0), streak)
    # crisp rim + subtle edge-only glow
    paste(img, (255, 255, 255), ring(m, 2))
    img = ImageChops.add(img, glow_layer(ring(m, 2), (200, 230, 255), 8, 0.5))
    return img


def render_glass(word, tint=(205, 228, 248), dark=False, bgc=(24, 32, 46),
                 blobs=((150, 90, 130, (70, 110, 160)), (430, 210, 150, (110, 80, 150)), (300, 60, 110, (60, 140, 170)))):
    """Apple-style liquid glass: refracted/blurred backdrop + tinted translucent
    body + bright edge lensing + specular sweep. Mirrors the JSX liquidGlass."""
    bgimg = bg(bgc)
    d = ImageDraw.Draw(bgimg)
    for (cx, cy, r, col) in blobs:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    bgimg = bgimg.filter(ImageFilter.GaussianBlur(45))
    m, _ = mask_of(word, fit_size(word))
    img = bgimg.copy()
    sh = fill_rgb(m, (0, 0, 0)).filter(ImageFilter.GaussianBlur(14))
    img = ImageChops.subtract(img, ImageChops.offset(sh, 8, 12).point(lambda v: int(v * (0.6 if dark else 0.45))))
    refr = ImageChops.offset(bgimg, 7, -7)
    arr = np.asarray(refr).astype(np.float32)
    if dark:
        ys = np.linspace(0.95, 0.32, H)[:, None, None]
        glass = np.clip(arr * 0.5 + np.array(tint) * 0.55 * ys, 0, 255).astype(np.uint8)
        blend = 0.95
        edge_hi = (235, 240, 248)
    else:
        ys = np.linspace(1.35, 0.72, H)[:, None, None]
        glass = np.clip(arr * 0.42 + np.array(tint) * 0.58 * ys, 0, 255).astype(np.uint8)
        blend = 0.9
        edge_hi = (255, 255, 255)
    body = img.copy(); body.paste(Image.fromarray(glass), (0, 0), m)
    img = Image.blend(img, body, blend)
    emb = emboss(img.copy(), m, 122, edge_hi, 1.5, 4, shadow_color=(15, 25, 40))
    img.paste(emb, (0, 0), m)
    streak = Image.new("L", (W, H), 0)
    ImageDraw.Draw(streak).polygon([(150, 0), (250, 0), (140, H), (40, H)], fill=130)
    streak = ImageChops.multiply(streak.filter(ImageFilter.GaussianBlur(16)), m)
    img.paste(Image.new("RGB", (W, H), (255, 255, 255)), (0, 0), streak)
    paste(img, edge_hi, ring(m, 2))
    img = ImageChops.add(img, glow_layer(ring(m, 2), tuple(min(255, c + 30) for c in tint), 8, 0.5))
    return img


_GLASS_BG = ((130, 70, 150, (120, 70, 160)), (430, 220, 160, (60, 150, 170)), (300, 50, 120, (200, 90, 140)))
def r_lg_clear():    return render_glass("CLEAR", (228, 238, 248), False)
def r_lg_regular():  return render_glass("REGULAR", (205, 222, 240), False)
def r_lg_dark():     return render_glass("DARK", (44, 52, 64), True, bgc=(16, 18, 26))
def r_lg_frost():    return render_glass("FROST", (240, 244, 250), False)
def r_lg_azure():    return render_glass("AZURE", (170, 205, 245), False, blobs=_GLASS_BG)
def r_lg_mint():     return render_glass("MINT", (180, 235, 212), False, blobs=_GLASS_BG)
def r_lg_rose():     return render_glass("ROSE", (245, 200, 220), False, blobs=_GLASS_BG)
def r_lg_amber():    return render_glass("AMBER", (245, 222, 175), False, blobs=_GLASS_BG)
def r_lg_violet():   return render_glass("VIOLET", (210, 195, 245), False, blobs=_GLASS_BG)
def r_lg_graphite(): return render_glass("GRAPHITE", (58, 62, 72), True, bgc=(14, 15, 20))


def r_kinetic():
    img = bg((24, 26, 34))
    for i, a in enumerate([0.12, 0.22, 0.4]):
        mm, _ = mask_of("KINETIC", fit_size("KINETIC", 430))
        mm = ImageChops.offset(mm, -(i + 1) * 16, 0)
        img = Image.blend(img, ImageChops.add(img, fill_rgb(mm, (90, 170, 255))), a)
    m, _ = mask_of("KINETIC", fit_size("KINETIC", 430))
    sh = fill_rgb(m, (0, 0, 0)).filter(ImageFilter.GaussianBlur(8))
    img = ImageChops.subtract(img, ImageChops.offset(sh, 4, 6).point(lambda v: int(v * .5)))
    paste(img, (245, 248, 255), m)
    return img


STYLES = [
    ("chrome_y2k", "Chrome Y2K", r_chrome), ("gold_luxury", "Gold Luxury", r_gold),
    ("variable_kinetic", "Variable Kinetic", r_kinetic), ("neon_cyberpunk", "Neon Cyberpunk", r_neon),
    ("retro_marquee", "Retro Marquee", r_marquee), ("extrude_3d", "3D Extrude", r_3d),
    ("glitch_vhs", "Glitch VHS", r_glitch), ("fluid_morph", "Fluid Morph", r_fluid),
    ("gradient_bold", "Gradient Bold", r_gradient_bold), ("outline_bubble", "Bubble Y2K", r_outline),
    ("platinum", "Platinum", r_platinum), ("rose_gold", "Rose Gold", r_rose),
    ("black_gold", "Black & Gold", r_black_gold), ("diamond", "Diamond", r_diamond),
    ("champagne", "Champagne", r_champagne), ("emerald", "Emerald Gem", r_emerald),
    ("sapphire", "Sapphire Gem", r_sapphire), ("royal_velvet", "Royal Velvet", r_royal_velvet),
    ("copper_bronze", "Copper Bronze", r_copper), ("marble_gold", "Marble Gold", r_marble),
    ("ruby", "Ruby Gem", r_ruby), ("amethyst", "Amethyst Gem", r_amethyst),
    ("onyx_classic", "Onyx Gloss", r_onyx_classic), ("onyx", "Onyx Black", r_onyx), ("pearl", "Pearl", r_pearl),
    ("titanium", "Titanium", r_titanium), ("liquid_gold", "Liquid Gold", r_liquidgold),
    ("frosted_glass", "Liquid Glass", r_frosted), ("holographic", "Holographic", r_holographic),
    ("neon_gold", "Neon Gold", r_neon_gold), ("navy_gold", "Navy & Gold", r_navy_gold),
    ("onyx_sapphire", "Onyx Sapphire", r_onyx_sapphire), ("onyx_emerald", "Onyx Emerald", r_onyx_emerald),
    ("onyx_ruby", "Onyx Ruby", r_onyx_ruby), ("onyx_amethyst", "Onyx Amethyst", r_onyx_amethyst),
    ("onyx_gold", "Onyx Gold", r_onyx_gold), ("onyx_teal", "Onyx Teal", r_onyx_teal),
    ("teal_aqua", "Aqua Gloss", r_teal_aqua), ("teal_turquoise", "Turquoise Gloss", r_teal_turquoise),
    ("teal_cyan", "Cyan Gloss", r_teal_cyan), ("teal_mint", "Mint Gloss", r_teal_mint),
    ("teal_lagoon", "Lagoon Gloss", r_teal_lagoon), ("teal_seafoam", "Seafoam Gloss", r_teal_seafoam),
    ("teal_petrol", "Petrol Gloss", r_teal_petrol), ("teal_tiffany", "Tiffany Gloss", r_teal_tiffany),
    ("teal_spearmint", "Spearmint Gloss", r_teal_spearmint), ("teal_ice", "Ice Gloss", r_teal_ice),
    ("lg_clear", "Glass Clear", r_lg_clear), ("lg_regular", "Glass Regular", r_lg_regular),
    ("lg_dark", "Glass Dark", r_lg_dark), ("lg_frost", "Glass Frost", r_lg_frost),
    ("lg_azure", "Glass Azure", r_lg_azure), ("lg_mint", "Glass Mint", r_lg_mint),
    ("lg_rose", "Glass Rose", r_lg_rose), ("lg_amber", "Glass Amber", r_lg_amber),
    ("lg_violet", "Glass Violet", r_lg_violet), ("lg_graphite", "Glass Graphite", r_lg_graphite),
]


def sheet(items, path, cols=2):
    rows = (len(items) + cols - 1) // cols
    pad = 14
    s = Image.new("RGB", (cols * W + pad * (cols + 1), rows * H + pad * (rows + 1)), (12, 13, 16))
    for i, (img, name) in enumerate(items):
        r, c = divmod(i, cols)
        s.paste(img, (pad + c * (W + pad), pad + r * (H + pad)))
    s.save(path)
    return path


def main():
    rendered = []
    for sid, name, fn in STYLES:
        try:
            img = label(fn().convert("RGB"), name)
        except Exception as e:
            img = label(bg(), name + "  (err: %s)" % e)
        img.save(os.path.join(OUT, sid + ".png"))
        rendered.append((img, name))
    sheet(rendered[0:10], "/tmp/sheet_trend.png")
    sheet(rendered[10:20], "/tmp/sheet_luxe1.png")
    sheet(rendered[20:30], "/tmp/sheet_luxe2.png")
    # Onyx family sheet: original Onyx Black + the 6 colour variants
    idx = dict((s[0], i) for i, s in enumerate(STYLES))
    onyx_ids = ["onyx_classic", "onyx", "onyx_sapphire", "onyx_emerald", "onyx_ruby", "onyx_amethyst", "onyx_gold", "onyx_teal"]
    sheet([rendered[idx[i]] for i in onyx_ids], "/tmp/sheet_onyx.png")
    teal_ids = ["onyx_teal", "teal_aqua", "teal_turquoise", "teal_cyan", "teal_mint", "teal_lagoon",
                "teal_seafoam", "teal_petrol", "teal_tiffany", "teal_spearmint", "teal_ice"]
    sheet([rendered[idx[i]] for i in teal_ids], "/tmp/sheet_teal.png")
    glass_ids = ["lg_clear", "lg_regular", "lg_dark", "lg_frost", "lg_azure", "lg_mint",
                 "lg_rose", "lg_amber", "lg_violet", "lg_graphite"]
    sheet([rendered[idx[i]] for i in glass_ids], "/tmp/sheet_glass.png")
    print("done:", len(rendered), "renders ->", OUT)


if __name__ == "__main__":
    main()
