# Changelog

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
