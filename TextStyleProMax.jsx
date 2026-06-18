/**********************************************************************************
 * Text Style Pro Max — Trending Text Styles for After Effects
 * ------------------------------------------------------------------------------
 * A dockable ScriptUI panel that applies a curated library of trend-driven text
 * looks to your selected text layers, with a live thumbnail preview gallery,
 * adjustable color / intensity, favorites and search.
 *
 * Every style is built from NATIVE After Effects layer styles + effects using
 * matchNames (locale-independent) — no third-party plugins required, no canned
 * .ffx presets. Each recipe is hand-tuned and wrapped in a single undo group.
 *
 * Install:  copy this file (and the /assets folder next to it) into
 *           …/Support Files/Scripts/ScriptUI Panels/  then relaunch AE and open
 *           it from the Window menu. (Enable "Allow Scripts to Write Files…".)
 *
 * Target:   After Effects 2024 (24.x) or newer.
 **********************************************************************************/

(function (thisObj) {
    "use strict";

    // -------------------------------------------------------------------------
    // 0. Constants & small utilities
    // -------------------------------------------------------------------------
    var SCRIPT_NAME = "Text Style Pro Max";
    var SCRIPT_VERSION = "1.0.0";

    // Layer-style group on every layer.
    var LS_GROUP = "ADBE Layer Styles";
    var LS_BLEND = "ADBE Blend Options Group";

    // Resolve where this script lives so we can find /assets/thumbnails.
    var SCRIPT_FILE = (function () {
        try { return new File($.fileName); } catch (e) { return null; }
    })();
    var SCRIPT_DIR = SCRIPT_FILE ? SCRIPT_FILE.parent : Folder.current;
    var THUMB_DIR = new Folder(SCRIPT_DIR.fsName + "/assets/thumbnails");

    // Persistent prefs (favorites + last options).
    var PREF_FILE = new File(Folder.userData.fsName + "/TextStyleProMax_prefs.json");

    function clamp(v, lo, hi) { return v < lo ? lo : (v > hi ? hi : v); }

    // Hex "#RRGGBB" -> normalized [r,g,b] (0..1) as AE expects.
    function hexToRgb(hex) {
        hex = ("" + hex).replace("#", "");
        if (hex.length === 3) hex = hex.charAt(0) + hex.charAt(0) + hex.charAt(1) +
            hex.charAt(1) + hex.charAt(2) + hex.charAt(2);
        var r = parseInt(hex.substr(0, 2), 16);
        var g = parseInt(hex.substr(2, 2), 16);
        var b = parseInt(hex.substr(4, 2), 16);
        if (isNaN(r) || isNaN(g) || isNaN(b)) return [1, 1, 1];
        return [r / 255, g / 255, b / 255];
    }

    function rgbToHex(rgb) {
        function h(v) {
            var s = Math.round(clamp(v, 0, 1) * 255).toString(16);
            return s.length === 1 ? "0" + s : s;
        }
        return "#" + h(rgb[0]) + h(rgb[1]) + h(rgb[2]);
    }

    // Mix two normalized colors. f=0 -> a, f=1 -> b.
    function mix(a, b, f) {
        return [a[0] + (b[0] - a[0]) * f,
                a[1] + (b[1] - a[1]) * f,
                a[2] + (b[2] - a[2]) * f];
    }

    // Lighten / darken a normalized color.
    function shade(c, f) { // f>0 lighten toward white, f<0 darken toward black
        if (f >= 0) return mix(c, [1, 1, 1], f);
        return mix(c, [0, 0, 0], -f);
    }

    function logErr(where, e) {
        $.writeln("[" + SCRIPT_NAME + "] " + where + ": " + (e && e.toString ? e.toString() : e));
    }

    // -------------------------------------------------------------------------
    // 1. Low-level AE property helpers (defensive — never throw upward)
    // -------------------------------------------------------------------------

    // Add (or fetch existing) a layer style by its "enabled" matchName,
    // e.g. "dropShadow/enabled". Returns the style PropertyGroup or null.
    function addStyle(layer, enabledMatch) {
        try {
            var ls = layer.property(LS_GROUP);
            if (!ls) return null;
            // The style group's matchName is the prefix before "/enabled".
            var groupMatch = enabledMatch.replace(/\/enabled$/, "");
            // Already present?
            for (var i = 1; i <= ls.numProperties; i++) {
                var p = ls.property(i);
                if (p && (p.matchName === groupMatch || p.matchName === enabledMatch)) return p;
            }
            if (ls.canAddProperty(enabledMatch)) return ls.addProperty(enabledMatch);
            if (ls.canAddProperty(groupMatch)) return ls.addProperty(groupMatch);
        } catch (e) { logErr("addStyle " + enabledMatch, e); }
        return null;
    }

    // Set a property (by matchName) on a group, swallowing failures so one bad
    // property can't abort a whole style.
    function setP(group, matchName, value) {
        if (!group) return;
        try {
            var p = group.property(matchName);
            if (p && typeof p.setValue === "function") p.setValue(value);
        } catch (e) { logErr("setP " + matchName, e); }
    }

    // Apply an effect by matchName, returns the effect or null.
    function addEffect(layer, matchName, niceName) {
        try {
            var fx = layer.property("ADBE Effect Parade");
            if (!fx || !fx.canAddProperty(matchName)) return null;
            var e = fx.addProperty(matchName);
            if (niceName) { try { e.name = niceName; } catch (er) {} }
            return e;
        } catch (e) { logErr("addEffect " + matchName, e); }
        return null;
    }

    // Set an effect property by 1-based index (effect params are most reliable
    // by index across locales).
    function setFx(effect, index, value) {
        if (!effect) return;
        try { effect.property(index).setValue(value); }
        catch (e) { logErr("setFx[" + index + "]", e); }
    }

    function setFxExpr(effect, index, expr) {
        if (!effect) return;
        try { effect.property(index).expression = expr; }
        catch (e) { logErr("setFxExpr[" + index + "]", e); }
    }

    // Fill-opacity lives in Blending Options; used by the outline style.
    function setFillOpacity(layer, pct) {
        try {
            var ls = layer.property(LS_GROUP);
            var bo = ls ? ls.property(LS_BLEND) : null;
            if (bo) setP(bo, "ADBE Layer Fill Opacity2", pct);
        } catch (e) { logErr("setFillOpacity", e); }
    }

    // -------------------------------------------------------------------------
    // 2. Re-usable style "ingredients" (parametrized by options)
    //    opts: { primary:[r,g,b], secondary:[r,g,b], intensity:0..2 }
    // -------------------------------------------------------------------------

    function ingGradientOverlay(layer, angle, opacity, blendMode) {
        // Uses AE's default black->white gradient as a metallic ramp; we only
        // drive angle / opacity / blend because custom gradient stops aren't
        // script-settable on layer styles.
        var g = addStyle(layer, "gradientFill/enabled");
        if (!g) return;
        setP(g, "gradientFill/opacity", opacity == null ? 100 : opacity);
        setP(g, "gradientFill/angle", angle == null ? 90 : angle);
        if (blendMode != null) setP(g, "gradientFill/mode2", blendMode);
        setP(g, "gradientFill/scale", 100);
    }

    function ingColorOverlay(layer, color, opacity, blendMode) {
        var c = addStyle(layer, "solidFill/enabled");
        if (!c) return;
        setP(c, "solidFill/color", color);
        setP(c, "solidFill/opacity", opacity == null ? 100 : opacity);
        if (blendMode != null) setP(c, "solidFill/mode2", blendMode);
    }

    function ingBevel(layer, hi, lo, depth, size, soften, angle, altitude) {
        var b = addStyle(layer, "bevelEmboss/enabled");
        if (!b) return;
        setP(b, "bevelEmboss/bevelStyle", 1);       // Inner Bevel
        setP(b, "bevelEmboss/bevelTechnique", 2);   // Chisel Hard (crisp metal)
        setP(b, "bevelEmboss/strengthRatio", depth);// Depth %
        setP(b, "bevelEmboss/blur", size);          // Size
        setP(b, "bevelEmboss/softness", soften || 0);
        setP(b, "bevelEmboss/useGlobalAngle", false);
        setP(b, "bevelEmboss/localLightingAngle", angle == null ? 120 : angle);
        setP(b, "bevelEmboss/localLightingAltitude", altitude == null ? 32 : altitude);
        setP(b, "bevelEmboss/highlightColor", hi || [1, 1, 1]);
        setP(b, "bevelEmboss/highlightOpacity", 90);
        setP(b, "bevelEmboss/shadowColor", lo || [0, 0, 0]);
        setP(b, "bevelEmboss/shadowOpacity", 70);
    }

    function ingSatin(layer, color, opacity) {
        var s = addStyle(layer, "chromeFX/enabled");
        if (!s) return;
        setP(s, "chromeFX/color", color || [1, 1, 1]);
        setP(s, "chromeFX/opacity", opacity == null ? 35 : opacity);
        setP(s, "chromeFX/mode2", 3); // Screen-ish sheen
        setP(s, "chromeFX/blur", 18);
        setP(s, "chromeFX/distance", 16);
        setP(s, "chromeFX/invert", true);
    }

    function ingStroke(layer, color, size, position, opacity) {
        var s = addStyle(layer, "frameFX/enabled");
        if (!s) return;
        setP(s, "frameFX/color", color);
        setP(s, "frameFX/size", size);
        setP(s, "frameFX/opacity", opacity == null ? 100 : opacity);
        setP(s, "frameFX/style", position == null ? 2 : position); // 1=out 2=center 3=in
    }

    function ingDropShadow(layer, color, opacity, distance, size, angle) {
        var d = addStyle(layer, "dropShadow/enabled");
        if (!d) return;
        setP(d, "dropShadow/color", color || [0, 0, 0]);
        setP(d, "dropShadow/opacity", opacity == null ? 60 : opacity);
        setP(d, "dropShadow/useGlobalAngle", false);
        setP(d, "dropShadow/localLightingAngle", angle == null ? 120 : angle);
        setP(d, "dropShadow/distance", distance == null ? 10 : distance);
        setP(d, "dropShadow/blur", size == null ? 12 : size);
    }

    function ingInnerShadow(layer, color, opacity, distance, size) {
        var d = addStyle(layer, "innerShadow/enabled");
        if (!d) return;
        setP(d, "innerShadow/color", color || [0, 0, 0]);
        setP(d, "innerShadow/opacity", opacity == null ? 50 : opacity);
        setP(d, "innerShadow/distance", distance == null ? 4 : distance);
        setP(d, "innerShadow/blur", size == null ? 6 : size);
    }

    function ingOuterGlow(layer, color, opacity, size, spread) {
        var g = addStyle(layer, "outerGlow/enabled");
        if (!g) return;
        setP(g, "outerGlow/AEColorChoice", 1); // single color (script-settable)
        setP(g, "outerGlow/color", color);
        setP(g, "outerGlow/opacity", opacity == null ? 90 : opacity);
        setP(g, "outerGlow/blur", size == null ? 30 : size);
        setP(g, "outerGlow/chokeMatte", spread == null ? 6 : spread);
        setP(g, "outerGlow/mode2", 3); // Screen
    }

    function ingInnerGlow(layer, color, opacity, size) {
        var g = addStyle(layer, "innerGlow/enabled");
        if (!g) return;
        setP(g, "innerGlow/AEColorChoice", 1);
        setP(g, "innerGlow/color", color);
        setP(g, "innerGlow/opacity", opacity == null ? 80 : opacity);
        setP(g, "innerGlow/blur", size == null ? 8 : size);
        setP(g, "innerGlow/mode2", 3);
    }

    // Glow EFFECT ("ADBE Glo2"). Param indices are stable:
    // 2 Glow Threshold, 3 Glow Radius, 4 Glow Intensity, 6 Glow Colors,
    // 8 Color A, 9 Color B.
    function ingGlowFx(layer, radius, intensity, threshold, name) {
        var g = addEffect(layer, "ADBE Glo2", name || "Glow");
        if (!g) return null;
        setFx(g, 2, threshold == null ? 50 : threshold);
        setFx(g, 3, radius == null ? 40 : radius);
        setFx(g, 4, intensity == null ? 1.5 : intensity);
        return g;
    }

    // Tritone ("ADBE Tritone") — maps luminance to 2/3 colors. The trick that
    // lets us build a true 2-colour gradient across text: combine with a b/w
    // Gradient Overlay. Indices: 2 Highlights, 3 Midtones, 4 Shadows, 5 Blend.
    function ingTritone(layer, shadows, highlights, midtones) {
        var t = addEffect(layer, "ADBE Tritone", "Color Map");
        if (!t) return;
        setFx(t, 2, highlights);
        setFx(t, 4, shadows);
        if (midtones) setFx(t, 3, midtones);
    }

    // -------------------------------------------------------------------------
    // 3. Text animator helper (kinetic reveal)
    // -------------------------------------------------------------------------
    function addKineticAnimator(layer) {
        try {
            var animators = layer.property("ADBE Text Properties").property("ADBE Text Animators");
            var anim = animators.addProperty("ADBE Text Animator");
            anim.name = "Kinetic In";
            var props = anim.property("ADBE Text Animator Properties");
            // Position Y, Scale, Opacity, Blur
            var pos = props.addProperty("ADBE Text Position 3D");
            pos.setValue([0, 120, 0]);
            var scl = props.addProperty("ADBE Text Scale 3D");
            scl.setValue([60, 60, 100]);
            var op = props.addProperty("ADBE Text Opacity");
            op.setValue(0);
            var blur = props.addProperty("ADBE Text Blur");
            try { blur.setValue([0, 40]); } catch (e) { try { blur.setValue(40); } catch (e2) {} }

            // Range selector keyframed to sweep across the text. We animate the
            // selector Offset from -100 -> 100, which reveals characters in
            // sequence regardless of the selector's "based on" / shape defaults.
            var sel = anim.property("ADBE Text Selectors").property("ADBE Text Selector");
            var offset = null;
            try { offset = sel.property("ADBE Text Percent Offset"); } catch (e) {}
            if (offset) {
                var t0 = layer.containingComp.time;
                var dur = 0.8;
                offset.setValueAtTime(t0, -100);
                offset.setValueAtTime(t0 + dur, 100);
                easeKeys(offset);
            }
        } catch (e) { logErr("addKineticAnimator", e); }
    }

    function easeKeys(prop) {
        try {
            for (var i = 1; i <= prop.numKeys; i++) {
                prop.setInterpolationTypeAtKey(i, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
            }
            var n = prop.numKeys;
            if (n >= 2) {
                var easeIn = new KeyframeEase(0, 80);
                var easeOut = new KeyframeEase(0, 80);
                prop.setTemporalEaseAtKey(1, [easeOut], [easeOut]);
                prop.setTemporalEaseAtKey(n, [easeIn], [easeIn]);
            }
        } catch (e) { logErr("easeKeys", e); }
    }

    // Faux-3D extrude by stacking offset duplicates behind the source layer.
    function build3DExtrude(layer, faceColor, sideColor, steps, dx, dy) {
        var comp = layer.containingComp;
        var made = [];
        try {
            for (var i = steps; i >= 1; i--) {
                var dup = layer.duplicate();
                dup.moveAfter(layer); // behind the original face
                var f = i / steps;
                ingColorOverlay(dup, shade(sideColor, -0.15 * (1 - f)), 100);
                var p = dup.property("ADBE Transform Group").property("ADBE Position");
                var base = p.value;
                p.setValue([base[0] + dx * i, base[1] + dy * i]);
                dup.name = layer.name + " ext " + i;
                made.push(dup);
            }
        } catch (e) { logErr("build3DExtrude", e); }
        // Face on top.
        ingColorOverlay(layer, faceColor, 100);
        ingBevel(layer, shade(faceColor, 0.4), shade(faceColor, -0.4), 120, 3, 0, 120, 40);
        return made;
    }

    // -------------------------------------------------------------------------
    // 4. THE STYLE LIBRARY  (ordered newest/hottest first)
    //    Each: id, name, cat, badge, desc, apply(layer, opts)
    // -------------------------------------------------------------------------
    var CATEGORIES = ["All", "Metal", "Neon", "3D", "Retro", "Social", "FX", "Favorites"];

    var STYLES = [
        {
            id: "chrome_y2k", name: "Chrome Y2K", cat: "Metal", badge: "NEW",
            desc: "Liquid metal / mirror chrome. Gradient + chisel bevel + satin sheen.",
            apply: function (layer, o) {
                ingGradientOverlay(layer, 90, 100, null);
                ingColorOverlay(layer, mix(o.primary, [0.78, 0.83, 0.92], 0.55), 35, 9); // soft-light tint
                ingBevel(layer, [1, 1, 1], shade(o.primary, -0.85), 220 * o.intensity, 5, 0, 118, 30);
                ingSatin(layer, [1, 1, 1], 30);
                ingInnerShadow(layer, [0.05, 0.07, 0.12], 45, 3, 5);
                ingStroke(layer, shade(o.primary, -0.4), 2, 3, 60);
                ingDropShadow(layer, [0, 0, 0], 55, 12, 16, 120);
                ingGlowFx(layer, 22, 1.1 * o.intensity, 65, "Chrome Bloom");
            }
        },
        {
            id: "gold_luxury", name: "Gold Luxury", cat: "Metal", badge: "HOT",
            desc: "Royal gold foil with warm bevel, satin and a soft golden bloom.",
            apply: function (layer, o) {
                var base = o._primaryIsDefault ? hexToRgb("#E6B450") : o.primary;
                ingColorOverlay(layer, base, 100);
                ingGradientOverlay(layer, 90, 55, 9); // soft-light metallic banding
                ingBevel(layer, hexToRgb("#FFF4CC"), hexToRgb("#5E3D0C"), 200 * o.intensity, 4, 0, 118, 34);
                ingSatin(layer, hexToRgb("#FFE9A8"), 28);
                ingOuterGlow(layer, hexToRgb("#FFCB5E"), 60, 26 * o.intensity, 4);
                ingStroke(layer, hexToRgb("#7A521A"), 2, 3, 80);
                ingDropShadow(layer, [0.04, 0.02, 0], 65, 10, 14, 120);
            }
        },
        {
            id: "variable_kinetic", name: "Variable Kinetic", cat: "Social", badge: "AE 2026",
            desc: "Bold flat look + a per-character kinetic reveal animation (in).",
            anim: true,
            desc2: "Adds keyframes at the playhead.",
            apply: function (layer, o) {
                ingColorOverlay(layer, o._primaryIsDefault ? hexToRgb("#F2F4FA") : o.primary, 100);
                ingDropShadow(layer, shade(o.secondary, -0.2), 40, 6, 10, 115);
                addKineticAnimator(layer);
            }
        },
        {
            id: "neon_cyberpunk", name: "Neon Cyberpunk", cat: "Neon", badge: "HOT",
            desc: "Deep-glow neon tube: colored stroke, inner core, layered outer glow.",
            apply: function (layer, o) {
                var neon = o._primaryIsDefault ? hexToRgb("#18E0FF") : o.primary;
                ingColorOverlay(layer, shade(neon, 0.25), 100);
                ingStroke(layer, neon, 3, 2, 100);
                ingInnerGlow(layer, [1, 1, 1], 85, 6);
                ingOuterGlow(layer, neon, 100, 45 * o.intensity, 8);
                ingDropShadow(layer, neon, 70, 0, 30, 90);
                ingGlowFx(layer, 60 * o.intensity, 2.2, 35, "Neon Bloom");
                ingGlowFx(layer, 18, 1.4, 60, "Neon Core");
            }
        },
        {
            id: "retro_marquee", name: "Retro Marquee", cat: "Retro", badge: "RETRO",
            desc: "Bubbly bulb-sign letters: smooth round bevel, warm glow, ring stroke.",
            apply: function (layer, o) {
                var c = o._primaryIsDefault ? hexToRgb("#A646F0") : o.primary;
                ingColorOverlay(layer, c, 100);
                // rounded bevel for the bulb body
                var b = addStyle(layer, "bevelEmboss/enabled");
                if (b) {
                    setP(b, "bevelEmboss/bevelStyle", 1);
                    setP(b, "bevelEmboss/bevelTechnique", 0); // Smooth (round)
                    setP(b, "bevelEmboss/strengthRatio", 160 * o.intensity);
                    setP(b, "bevelEmboss/blur", 9);
                    setP(b, "bevelEmboss/highlightColor", [1, 1, 1]);
                    setP(b, "bevelEmboss/highlightOpacity", 85);
                    setP(b, "bevelEmboss/shadowColor", shade(c, -0.7));
                    setP(b, "bevelEmboss/shadowOpacity", 70);
                    setP(b, "bevelEmboss/useGlobalAngle", false);
                    setP(b, "bevelEmboss/localLightingAngle", 120);
                    setP(b, "bevelEmboss/localLightingAltitude", 45);
                }
                ingStroke(layer, shade(c, 0.5), 4, 1, 90);
                ingOuterGlow(layer, c, 90, 40 * o.intensity, 4);
                ingDropShadow(layer, [0, 0, 0], 60, 14, 18, 120);
            }
        },
        {
            id: "extrude_3d", name: "3D Extrude", cat: "3D", badge: "3D",
            desc: "Real stacked-duplicate extrusion (block letters) with a beveled face.",
            heavy: true,
            apply: function (layer, o) {
                var face = o._primaryIsDefault ? hexToRgb("#E9C39A") : o.primary;
                var side = o._secondaryIsDefault ? shade(face, -0.45) : o.secondary;
                var steps = Math.round(14 * o.intensity);
                steps = clamp(steps, 6, 30);
                build3DExtrude(layer, face, side, steps, 1.6, 1.6);
                ingDropShadow(layer, [0, 0, 0], 45, steps * 2, 24, 120);
            }
        },
        {
            id: "glitch_vhs", name: "Glitch VHS", cat: "FX", badge: "FX",
            desc: "Animated RGB-split + jitter (chromatic aberration) via duplicate channels.",
            heavy: true,
            apply: function (layer, o) {
                // Original stays white-ish core.
                ingColorOverlay(layer, [0.93, 0.93, 0.95], 100);
                var comp = layer.containingComp;

                function makeShift(tag, mixR, mixG, mixB, sx) {
                    var d = layer.duplicate();
                    d.moveBefore(layer);
                    d.name = layer.name + " " + tag;
                    var cm = addEffect(d, "ADBE Channel Mixer", "Split " + tag);
                    // Channel Mixer indices: 1 R-R,2 R-G,3 R-B,... we zero unwanted.
                    try {
                        setFx(cm, 1, mixR[0]); setFx(cm, 2, mixR[1]); setFx(cm, 3, mixR[2]);
                        setFx(cm, 6, mixG[0]); setFx(cm, 7, mixG[1]); setFx(cm, 8, mixG[2]);
                        setFx(cm, 11, mixB[0]); setFx(cm, 12, mixB[1]); setFx(cm, 13, mixB[2]);
                    } catch (e) {}
                    try { d.blendingMode = BlendingMode.SCREEN; } catch (e) {}
                    var p = d.property("ADBE Transform Group").property("ADBE Position");
                    var base = p.value;
                    p.setValue([base[0] + sx, base[1]]);
                    p.expression =
                        "seedRandom(index, true);\n" +
                        "p = posterizeTime(12); \n" +
                        "x = wiggle(8, " + (10 * o.intensity).toFixed(1) + ")[0];\n" +
                        "[x, value[1]];";
                    return d;
                }
                makeShift("R", [1, 0, 0], [0, 0, 0], [0, 0, 0], -8 * o.intensity);
                makeShift("B", [0, 0, 0], [0, 0, 0], [0, 0, 1], 8 * o.intensity);

                // Slice/displacement on the core.
                var tw = addEffect(layer, "ADBE Wave Warp", "Glitch Slice");
                if (tw) {
                    setFx(tw, 1, 8 * o.intensity); // wave height
                    setFx(tw, 2, 200);             // wave width
                    setFxExpr(tw, 4, "posterizeTime(8); time*220 + random()*360"); // direction churn
                }
                layer.property("ADBE Transform Group").property("ADBE Position").expression =
                    "seedRandom(index, true);\n" +
                    "p = posterizeTime(10);\n" +
                    "value + (random(-1,1) < 0.85 ? [0,0] : wiggle(20, " + (6 * o.intensity).toFixed(1) + ") - value);";
            }
        },
        {
            id: "fluid_morph", name: "Fluid Morph", cat: "FX", badge: "TREND",
            desc: "Liquid wobbling edges (animated Turbulent Displace) + glossy fill + glow.",
            apply: function (layer, o) {
                ingColorOverlay(layer, o._primaryIsDefault ? hexToRgb("#5B8CFF") : o.primary, 100);
                ingGradientOverlay(layer, 90, 45, 9);
                ingBevel(layer, [1, 1, 1], shade(o.primary, -0.6), 130 * o.intensity, 7, 6, 120, 50);
                ingOuterGlow(layer, o._secondaryIsDefault ? hexToRgb("#B852FF") : o.secondary, 80, 30 * o.intensity, 4);

                var td = addEffect(layer, "ADBE Turbulent Displace", "Liquid");
                if (td) {
                    setFx(td, 2, 22 * o.intensity); // amount
                    setFx(td, 3, 60);               // size
                    setFxExpr(td, 7, "time*120"); // evolution -> continuous flow
                }
                ingGlowFx(layer, 20 * o.intensity, 1.2, 55, "Sheen");
            }
        },
        {
            id: "gradient_bold", name: "Gradient Bold", cat: "Social", badge: "SOCIAL",
            desc: "Clean 2-color social gradient via b/w Gradient Overlay + Tritone mapping.",
            apply: function (layer, o) {
                var a = o._primaryIsDefault ? hexToRgb("#FF4696") : o.primary;
                var b = o._secondaryIsDefault ? hexToRgb("#785AFF") : o.secondary;
                ingColorOverlay(layer, [1, 1, 1], 100);          // white base for the ramp
                ingGradientOverlay(layer, 45, 100, null);        // b/w diagonal ramp
                ingTritone(layer, a, b, mix(a, b, 0.5));         // remap ramp to a->b
                ingDropShadow(layer, shade(a, -0.5), 35, 6, 10, 120);
            }
        },
        {
            id: "outline_bubble", name: "Outline Bubble", cat: "Retro", badge: "Y2K",
            desc: "Hollow Y2K sticker outline: zero fill, thick rounded stroke, soft shadow.",
            apply: function (layer, o) {
                setFillOpacity(layer, 0);
                var c = o._primaryIsDefault ? hexToRgb("#FF6EB4") : o.primary;
                ingStroke(layer, c, 6 * o.intensity, 1, 100);
                // a second, lighter offset stroke for a bubble outline read
                ingOuterGlow(layer, shade(c, 0.4), 40, 8, 0);
                ingDropShadow(layer, [0, 0, 0], 40, 8, 10, 120);
            }
        }
    ];

    function findStyle(id) {
        for (var i = 0; i < STYLES.length; i++) if (STYLES[i].id === id) return STYLES[i];
        return null;
    }

    // -------------------------------------------------------------------------
    // 5. Apply orchestration
    // -------------------------------------------------------------------------
    function getSelectedTextLayers() {
        var comp = app.project ? app.project.activeItem : null;
        var out = [];
        if (!comp || !(comp instanceof CompItem)) return { comp: null, layers: out };
        var sel = comp.selectedLayers;
        for (var i = 0; i < sel.length; i++) {
            if (sel[i] instanceof TextLayer) out.push(sel[i]);
        }
        return { comp: comp, layers: out };
    }

    function applyStyle(styleId, opts) {
        var style = findStyle(styleId);
        if (!style) return;
        var info = getSelectedTextLayers();
        if (!info.comp) { alert("Open a composition first."); return; }
        if (info.layers.length === 0) {
            alert("Select one or more TEXT layers, then click Apply.");
            return;
        }
        app.beginUndoGroup(SCRIPT_NAME + ": " + style.name);
        var ok = 0;
        try {
            for (var i = 0; i < info.layers.length; i++) {
                try { style.apply(info.layers[i], opts); ok++; }
                catch (e) { logErr("applyStyle " + style.id, e); }
            }
        } finally {
            app.endUndoGroup();
        }
        return ok;
    }

    // -------------------------------------------------------------------------
    // 6. Preferences (favorites + last options)
    // -------------------------------------------------------------------------
    var prefs = { favorites: [], primary: "#C9D2E0", secondary: "#785AFF", intensity: 100 };

    function loadPrefs() {
        try {
            if (PREF_FILE.exists) {
                PREF_FILE.open("r"); var txt = PREF_FILE.read(); PREF_FILE.close();
                var p = eval("(" + txt + ")");
                if (p) {
                    if (p.favorites) prefs.favorites = p.favorites;
                    if (p.primary) prefs.primary = p.primary;
                    if (p.secondary) prefs.secondary = p.secondary;
                    if (p.intensity) prefs.intensity = p.intensity;
                }
            }
        } catch (e) { logErr("loadPrefs", e); }
    }

    function savePrefs() {
        try {
            PREF_FILE.open("w");
            PREF_FILE.write('{"favorites":[' +
                map(prefs.favorites, function (f) { return '"' + f + '"'; }).join(",") +
                '],"primary":"' + prefs.primary + '","secondary":"' + prefs.secondary +
                '","intensity":' + prefs.intensity + '}');
            PREF_FILE.close();
        } catch (e) { logErr("savePrefs", e); }
    }

    function map(arr, fn) { var o = []; for (var i = 0; i < arr.length; i++) o.push(fn(arr[i])); return o; }
    function indexOf(arr, v) { for (var i = 0; i < arr.length; i++) if (arr[i] === v) return i; return -1; }
    function isFav(id) { return indexOf(prefs.favorites, id) !== -1; }
    function toggleFav(id) {
        var i = indexOf(prefs.favorites, id);
        if (i === -1) prefs.favorites.push(id); else prefs.favorites.splice(i, 1);
        savePrefs();
    }

    // -------------------------------------------------------------------------
    // 7. Simple color picker dialog (AE has no native OS picker in ScriptUI)
    // -------------------------------------------------------------------------
    function colorDialog(startHex) {
        var rgb = hexToRgb(startHex);
        var dlg = new Window("dialog", "Pick Color");
        dlg.alignChildren = "fill";
        var swatch = dlg.add("panel"); swatch.preferredSize = [220, 40];
        function paintSwatch() {
            swatch.graphics.backgroundColor =
                swatch.graphics.newBrush(swatch.graphics.BrushType.SOLID_COLOR, [rgb[0], rgb[1], rgb[2], 1]);
        }
        var rows = [["R", 0], ["G", 1], ["B", 2]];
        var sliders = [];
        for (var i = 0; i < rows.length; i++) (function (idx) {
            var g = dlg.add("group");
            g.add("statictext", undefined, rows[idx][0]);
            var s = g.add("slider", undefined, rgb[idx] * 255, 0, 255);
            s.preferredSize = [160, 20];
            var t = g.add("edittext", undefined, "" + Math.round(rgb[idx] * 255));
            t.characters = 4;
            s.onChanging = function () { rgb[idx] = s.value / 255; t.text = "" + Math.round(s.value); paintSwatch(); hexT.text = rgbToHex(rgb); };
            t.onChange = function () { var v = clamp(parseInt(t.text, 10) || 0, 0, 255); s.value = v; rgb[idx] = v / 255; paintSwatch(); hexT.text = rgbToHex(rgb); };
            sliders.push(s);
        })(i);
        var hg = dlg.add("group"); hg.add("statictext", undefined, "Hex");
        var hexT = hg.add("edittext", undefined, rgbToHex(rgb)); hexT.characters = 8;
        hexT.onChange = function () {
            rgb = hexToRgb(hexT.text);
            for (var k = 0; k < 3; k++) sliders[k].value = rgb[k] * 255;
            paintSwatch();
        };
        var bg = dlg.add("group"); bg.alignment = "right";
        var ok = bg.add("button", undefined, "OK", { name: "ok" });
        bg.add("button", undefined, "Cancel", { name: "cancel" });
        paintSwatch();
        dlg.layout.layout(true);
        return dlg.show() === 1 ? rgbToHex(rgb) : null;
    }

    // -------------------------------------------------------------------------
    // 8. UI
    // -------------------------------------------------------------------------
    function buildUI(thisObj) {
        var pal = (thisObj instanceof Panel) ? thisObj :
            new Window("palette", SCRIPT_NAME + " " + SCRIPT_VERSION, undefined, { resizeable: true });
        pal.alignChildren = ["fill", "top"];
        pal.spacing = 6; pal.margins = 8;

        // --- Header ---
        var header = pal.add("group");
        header.alignment = ["fill", "top"];
        var title = header.add("statictext", undefined, SCRIPT_NAME);
        try { title.graphics.font = ScriptUI.newFont("dialog", "BOLD", 14); } catch (e) {}
        header.add("statictext", undefined, "v" + SCRIPT_VERSION).alignment = ["right", "center"];

        // --- Search + Category ---
        var bar = pal.add("group"); bar.alignment = ["fill", "top"];
        bar.add("statictext", undefined, "Find:");
        var search = bar.add("edittext", undefined, ""); search.characters = 12;
        bar.add("statictext", undefined, "Cat:");
        var catDD = bar.add("dropdownlist", undefined, CATEGORIES);
        catDD.selection = 0;

        // --- Gallery (scrollable) ---
        var galleryHost = pal.add("panel");
        galleryHost.alignment = ["fill", "fill"];
        galleryHost.alignChildren = ["fill", "top"];
        galleryHost.margins = 4;
        galleryHost.text = "Styles";
        var gallery = galleryHost.add("group");
        gallery.orientation = "column";
        gallery.alignChildren = ["fill", "top"];
        gallery.spacing = 4;
        gallery.maximumSize = [10000, 100000];

        // --- Selected preview + description ---
        var prev = pal.add("panel"); prev.text = "Preview";
        prev.alignment = ["fill", "top"]; prev.alignChildren = ["fill", "top"]; prev.margins = 6;
        var prevImg = null;
        try {
            var firstThumb = new File(THUMB_DIR.fsName + "/chrome_y2k.png");
            prevImg = prev.add("image", undefined, firstThumb.exists ? firstThumb : undefined);
        } catch (e) { prevImg = prev.add("statictext", undefined, "(preview)"); }
        var prevName = prev.add("statictext", undefined, "—");
        try { prevName.graphics.font = ScriptUI.newFont("dialog", "BOLD", 12); } catch (e) {}
        var prevDesc = prev.add("statictext", undefined, "Select a style above.", { multiline: true });
        prevDesc.preferredSize = [260, 42];

        // --- Options ---
        var opt = pal.add("panel"); opt.text = "Options";
        opt.alignment = ["fill", "top"]; opt.alignChildren = ["fill", "top"]; opt.margins = 6; opt.spacing = 4;

        var co = opt.add("group");
        co.add("statictext", undefined, "Primary");
        var primSw = co.add("button", undefined, "        "); primSw.preferredSize = [40, 20];
        var primHex = co.add("edittext", undefined, prefs.primary); primHex.characters = 8;
        co.add("statictext", undefined, "Secondary");
        var secSw = co.add("button", undefined, "        "); secSw.preferredSize = [40, 20];
        var secHex = co.add("edittext", undefined, prefs.secondary); secHex.characters = 8;

        var io = opt.add("group");
        io.add("statictext", undefined, "Intensity");
        var intSlider = io.add("slider", undefined, prefs.intensity, 25, 200);
        intSlider.preferredSize = [150, 20];
        var intVal = io.add("statictext", undefined, prefs.intensity + "%");
        intVal.preferredSize = [40, 20];

        function paintBtn(btn, hex) {
            try {
                var c = hexToRgb(hex);
                btn.graphics.backgroundColor = btn.graphics.newBrush(
                    btn.graphics.BrushType.SOLID_COLOR, [c[0], c[1], c[2], 1]);
            } catch (e) {}
        }
        paintBtn(primSw, prefs.primary); paintBtn(secSw, prefs.secondary);

        // --- Action buttons ---
        var actions = pal.add("group"); actions.alignment = ["fill", "bottom"];
        var applyBtn = actions.add("button", undefined, "Apply to Selected");
        applyBtn.alignment = ["fill", "center"];
        var favBtn = actions.add("button", undefined, "☆ Fav");
        favBtn.preferredSize = [60, 26];

        var status = pal.add("statictext", undefined, "Ready. Select a text layer.");
        status.alignment = ["fill", "bottom"];

        // ---- state ----
        var selectedId = null;
        var thumbButtons = [];

        function currentOpts() {
            var primIsDef = (primHex.text.toUpperCase() === "#C9D2E0");
            var secIsDef = (secHex.text.toUpperCase() === "#785AFF");
            return {
                primary: hexToRgb(primHex.text),
                secondary: hexToRgb(secHex.text),
                intensity: clamp(intSlider.value / 100, 0.25, 2),
                _primaryIsDefault: primIsDef,
                _secondaryIsDefault: secIsDef
            };
        }

        function selectStyle(style) {
            selectedId = style.id;
            prevName.text = style.name + "   [" + style.cat + (style.badge ? " · " + style.badge : "") + "]";
            prevDesc.text = style.desc + (style.anim ? "  (adds keyframes)" : "") +
                (style.heavy ? "  (creates extra layers)" : "");
            try {
                var f = new File(THUMB_DIR.fsName + "/" + style.id + ".png");
                if (f.exists && prevImg && prevImg.image !== undefined) prevImg.image = f;
            } catch (e) {}
            favBtn.text = isFav(style.id) ? "★ Fav" : "☆ Fav";
            status.text = "Selected: " + style.name;
        }

        function rebuildGallery() {
            // clear
            for (var i = gallery.children.length - 1; i >= 0; i--) gallery.remove(gallery.children[i]);
            thumbButtons = [];
            var cat = CATEGORIES[catDD.selection.index];
            var q = (search.text || "").toLowerCase();

            for (var s = 0; s < STYLES.length; s++) {
                var st = STYLES[s];
                if (cat === "Favorites") { if (!isFav(st.id)) continue; }
                else if (cat !== "All" && st.cat !== cat) continue;
                if (q && st.name.toLowerCase().indexOf(q) === -1 &&
                    st.desc.toLowerCase().indexOf(q) === -1 && st.cat.toLowerCase().indexOf(q) === -1) continue;

                var row = gallery.add("group");
                row.orientation = "row";
                row.alignment = ["fill", "top"];
                row.alignChildren = ["left", "center"];
                row.spacing = 8;

                var f = new File(THUMB_DIR.fsName + "/" + st.id + ".png");
                var btn;
                try {
                    btn = row.add("iconbutton", undefined, f.exists ? f : undefined, { style: "toolbutton", toggle: true });
                    btn.preferredSize = [120, 67];
                } catch (e) {
                    btn = row.add("button", undefined, st.name);
                }
                var lab = row.add("group"); lab.orientation = "column"; lab.alignChildren = ["left", "top"];
                var nm = lab.add("statictext", undefined, (isFav(st.id) ? "★ " : "") + st.name);
                try { nm.graphics.font = ScriptUI.newFont("dialog", "BOLD", 12); } catch (e) {}
                lab.add("statictext", undefined, st.cat + (st.badge ? "  ·  " + st.badge : ""));

                (function (style, button) {
                    button.onClick = function () { selectStyle(style); };
                    button.addEventListener("mousedown", function () { selectStyle(style); });
                })(st, btn);

                thumbButtons.push(btn);
            }
            if (gallery.children.length === 0) {
                gallery.add("statictext", undefined, "No styles match.");
            }
            pal.layout.layout(true);
            pal.layout.resize();
        }

        // ---- events ----
        catDD.onChange = rebuildGallery;
        search.onChanging = rebuildGallery;

        intSlider.onChanging = function () {
            intVal.text = Math.round(intSlider.value) + "%";
            prefs.intensity = Math.round(intSlider.value);
        };
        intSlider.onChange = function () { savePrefs(); };

        primSw.onClick = function () {
            var c = colorDialog(primHex.text); if (c) { primHex.text = c; paintBtn(primSw, c); prefs.primary = c; savePrefs(); }
        };
        secSw.onClick = function () {
            var c = colorDialog(secHex.text); if (c) { secHex.text = c; paintBtn(secSw, c); prefs.secondary = c; savePrefs(); }
        };
        primHex.onChange = function () { paintBtn(primSw, primHex.text); prefs.primary = primHex.text; savePrefs(); };
        secHex.onChange = function () { paintBtn(secSw, secHex.text); prefs.secondary = secHex.text; savePrefs(); };

        favBtn.onClick = function () {
            if (!selectedId) { status.text = "Select a style first."; return; }
            toggleFav(selectedId);
            favBtn.text = isFav(selectedId) ? "★ Fav" : "☆ Fav";
            rebuildGallery();
        };

        applyBtn.onClick = function () {
            if (!selectedId) { status.text = "Select a style first."; return; }
            var info = getSelectedTextLayers();
            if (info.layers.length === 0) { status.text = "⚠ Select text layer(s) first."; return; }
            var n = applyStyle(selectedId, currentOpts());
            status.text = "✔ Applied “" + findStyle(selectedId).name + "” to " + n + " layer(s).";
        };

        // initial
        rebuildGallery();
        if (STYLES.length) selectStyle(STYLES[0]);

        pal.onResizing = pal.onResize = function () { try { this.layout.resize(); } catch (e) {} };

        return pal;
    }

    // -------------------------------------------------------------------------
    // 9. Boot
    // -------------------------------------------------------------------------
    loadPrefs();
    if (!THUMB_DIR.exists) {
        // Non-fatal: panel still works, just without images.
        $.writeln("[" + SCRIPT_NAME + "] thumbnails not found at " + THUMB_DIR.fsName);
    }
    var ui = buildUI(thisObj);
    if (ui instanceof Window) {
        ui.center();
        ui.show();
    } else {
        ui.layout.layout(true);
    }

})(this);
