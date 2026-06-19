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


def r_onyx():
    img = bg((6, 6, 8))
    m, _ = mask_of("ONYX", fit_size("ONYX"))
    face = sheen(fill_rgb(m, (12, 12, 14)), m, 1.9, 0.5)
    face = emboss(face, m, 122, (200, 200, 210), 0.9, 3)
    img.paste(face, (0, 0), m)
    paste(img, hx("#26262C"), ring(m, 2))
    return img


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
    img = bg((20, 22, 28))
    m, _ = mask_of("OUTLINE", fit_size("OUTLINE"))
    sh = ring(m, 7).filter(ImageFilter.GaussianBlur(5))
    img = ImageChops.add(img, ImageChops.offset(fill_rgb(sh.point(lambda v: 255), (0, 0, 0)), 3, 6))
    paste(img, hx("#FF6EB4"), ring(m, 4))
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
        out[yy] = np.roll(arr[yy], int(8 * math.sin(yy / 14.0)))
    wob = Image.fromarray(out)
    a, b = hx("#5B8CFF"), hx("#B852FF")
    img = ImageChops.add(img, glow_layer(wob, b, 26, 0.8))
    face = emboss(sheen(fill_rgb(wob, tuple((a[k] + b[k]) // 2 for k in range(3))), wob, 1.35, 0.7), wob, 122, hx("#D8C0FF"), 0.8, 3)
    img.paste(face, (0, 0), wob)
    paste(img, hx("#7FA0FF"), ring(wob, 2))
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
    img = bg((20, 26, 34))
    m, _ = mask_of("GLASS", fit_size("GLASS"))
    tmp = img.copy(); paste(tmp, (205, 222, 238), m)
    img = Image.blend(img, tmp, 0.62)
    face = emboss(img.copy(), m, 122, (255, 255, 255), 1.0, 3)
    img.paste(face, (0, 0), m)
    paste(img, (255, 255, 255), ring(m, 2))
    return img


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
    ("gradient_bold", "Gradient Bold", r_gradient_bold), ("outline_bubble", "Outline Bubble", r_outline),
    ("platinum", "Platinum", r_platinum), ("rose_gold", "Rose Gold", r_rose),
    ("black_gold", "Black & Gold", r_black_gold), ("diamond", "Diamond", r_diamond),
    ("champagne", "Champagne", r_champagne), ("emerald", "Emerald Gem", r_emerald),
    ("sapphire", "Sapphire Gem", r_sapphire), ("royal_velvet", "Royal Velvet", r_royal_velvet),
    ("copper_bronze", "Copper Bronze", r_copper), ("marble_gold", "Marble Gold", r_marble),
    ("ruby", "Ruby Gem", r_ruby), ("amethyst", "Amethyst Gem", r_amethyst),
    ("onyx", "Onyx Gloss", r_onyx), ("pearl", "Pearl", r_pearl),
    ("titanium", "Titanium", r_titanium), ("liquid_gold", "Liquid Gold", r_liquidgold),
    ("frosted_glass", "Frosted Glass", r_frosted), ("holographic", "Holographic", r_holographic),
    ("neon_gold", "Neon Gold", r_neon_gold), ("navy_gold", "Navy & Gold", r_navy_gold),
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
    print("done:", len(rendered), "renders ->", OUT)


if __name__ == "__main__":
    main()
