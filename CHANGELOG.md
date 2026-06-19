# Changelog

## 2.9.0 — Teal spectrum family (+10)
- New "Teal" category with 10 premium glossy-lacquer styles across the teal
  spectrum: Aqua, Turquoise, Cyan, Mint, Lagoon, Seafoam, Petrol, Tiffany,
  Spearmint, Ice. Built on the loved onyxSurface look. Original Onyx Teal is
  unchanged. Library is now 47 styles.


## 2.8.1 — Restore the original Onyx
- Brought back the exact original Onyx recipe as "Onyx Gloss" (Classic) alongside
  the new specular "Onyx Black". Onyx family is now 8 (Classic + Black + Sapphire,
  Emerald, Ruby, Amethyst, Gold, Teal). Library is 37 styles.


## 2.8.0 — Onyx family (+6 premium colour variants)
- Added an "Onyx" category and 6 new premium glossy-lacquer variants of the
  loved Onyx look: Sapphire, Emerald, Ruby, Amethyst, Gold (black-gold) and Teal.
- Refactored Onyx into a reusable onyxSurface(accent) so any hue is one call;
  the base Onyx Black now also gets the specular shine. All respect the Primary
  colour override. Library is now 36 styles.


## 2.7.0 — Premium pass on every style
- Added a real specular shine (CC Light Sweep) to all metals & gems for true
  reflective highlights.
- Fluid Morph rebuilt: real 2-colour gradient body + animated wobbling edges
  (Turbulent Displace on the precomp) + specular sheen.
- "Outline Bubble" -> "Bubble Y2K": glossy puffy candy sticker (bright fill,
  rounded gloss bevel, thick dark outline, sticker shadow).
- Renderer updated to match (specular streaks, fluid gradient, bubble gloss).


## 2.6.0 — Liquid Glass redesigned (real glass, not faded text)
- Reworked "Frosted Glass" into a proper **Liquid Glass**: a clear gradient
  glass body (via gradient-in-letters), bright refractive bevel edges, an
  optional CC Glass refraction + CC Light Sweep specular streak, and an
  EDGE-ONLY bloom (high threshold) so the body stays crisp instead of being
  washed out by glow.
- Updated the preview renderer to show the new glass over a textured backdrop
  so the translucency/refraction reads.


## 2.5.0 — Real gradient INSIDE the letters (match the renders)
- The big gap between the preview renders and the AE output was the metallic
  GRADIENT: the renders fill the letters with a light->dark sheen, while the
  script used a flat fill. Metals & gems now build a real vertical gradient
  inside the glyphs (gradient solid + alpha track-matte + precompose) and then
  add Bevel Alpha + Glow + Drop Shadow on top.
- Gracefully falls back to the matted gradient solid if precompose is
  unavailable, so the gradient still shows.
- Applies to: Chrome, Gold, Platinum, Rose Gold, Champagne, Copper, Titanium,
  Liquid Gold, Pearl, and all gems (Diamond/Emerald/Sapphire/Ruby/Amethyst).
  Black & Gold, Royal Velvet and Onyx (already liked) are unchanged.


## 2.4.0 — Distinct, richer looks (Tritone removed from metals/gems)
- Root cause of "all styles look the same": the Tritone tone-map was overriding
  each style's base colour, flattening every metal/gem into a similar grey-ish
  tone. Removed Tritone from all metals and gems.
- Metals now keep their true fill colour as identity + a bright bevel sheen, a
  contrasting trim stroke, bloom and shadow (the formula from the well-liked
  Black & Gold / Onyx / Royal Velvet).
- Gems use a new faceted gemSurface (bevel + bright edge + strong coloured glow)
  so Ruby/Emerald/Sapphire/Amethyst/Diamond read clearly different.
- Cleaned up Pearl, Frosted Glass and Fluid Morph the same way. Onyx, Royal
  Velvet and Holographic (intentionally multi-colour) keep their tone-map.


## 2.3.0 — UI overhaul (scroll + previews fixed)
- Replaced the non-scrolling icon grid with a native **scrollable ListBox** —
  all 30 styles are now reachable.
- Fixed empty thumbnails: ScriptUI does not scale images, so the big 360px
  thumbs only showed a cropped corner in small buttons. Previews are now shown
  full-size (240px) in a dedicated Preview pane; the list is clean text + badge.
- Cleaner layout, double-click a list item to apply, clearer Options row, and a
  helpful note when "Allow Scripts to Write Files" is off (needed for previews).


## 2.2.0 — Luxury pack II (+10 styles, 30 total)
- Added 10 more premium styles: Ruby Gem, Amethyst Gem, Onyx Gloss, Pearl,
  Titanium, Liquid Gold, Frosted Glass, Holographic, Neon Gold, Navy & Gold.
- Library is now 30 styles; thumbnails regenerated & re-embedded.


## 2.1.0 — Luxury pack (+10 styles)
- Added a **Luxe** pack (10 new styles): Platinum, Rose Gold, Black & Gold,
  Diamond, Champagne, Emerald Gem, Sapphire Gem, Royal Velvet, Copper Bronze,
  Marble Gold.
- New categories **Luxe** and **Gem**; a marble texture helper (Fractal Noise
  clipped inside the letters via alpha matte).
- Library is now 20 styles; thumbnails regenerated & re-embedded.


## 2.0.0 — Engine rewrite (quality + reliability)
- **Critical fix:** layer styles can't be added by script (`addProperty` fails),
  which made the metallic styles look flat. The engine no longer uses layer
  styles at all.
- Rebuilt every style on reliably-scriptable techniques:
  - **Metals (Chrome/Gold/Fluid):** Bevel Alpha shading remapped to a metal
    palette with Tritone + Glow — real metallic shading, alpha preserved, no
    precomp.
  - **Gradient Bold:** a true directional Ramp clipped inside the letters via an
    alpha track-matte (`setTrackMatte`, AE 2023+).
  - **Neon / Outline / Retro:** the text layer's own fill/stroke (TextDocument)
    + stacked Glow effects.
  - **3D Extrude / Glitch:** real duplicated layers (extrude steps; RGB-split
    with wiggle/posterizeTime jitter).
- Added **Demo Comp** button: builds a ready-made, fully editable demo
  composition for the selected style (the in-AE "template").
- Added an **in-panel issue log** (⚠ button) surfacing any non-fatal errors so
  problems can be diagnosed without the ESTK console.

## 1.0.0
- Initial release: 10 trend styles, thumbnail gallery, search, categories,
  favorites, color/intensity, single-undo apply. (Layer-style based — superseded
  by 2.0.0.)
