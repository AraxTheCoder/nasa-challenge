# T137: Chemistry list scrolls; floating panels fold

- **Owner:** Mati  ·  **Status:** review
- **Branch:** `mati/T137-fold-panels`
- **Depends on / feeds:** T124 (floating panels, Jonathan), T93/T127 (chemistry list)

## Goal
1. The Chemistry dropdown never runs past the bottom of the window: it is capped at the space below its button and
   scrolls (on wide screens it had no cap since the T124 floating UI; the T127 presets made it longer).
2. Each floating panel group (Field, Map) can be folded to one line: a – button next to its ⠿ grip; folded it shows
   ⠿ + its name, a click opens it again. Remembered per browser. Status (build progress, messages) stays visible.

## Plan
- [x] chemistry.js: cap the open list to the window (on open and on resize); style.css: overflow-y auto.
- [x] hud.js: fold button by the grip, folded tab (grip + name), remembered in localStorage; style.css rules.
- [x] Light checks only (node syntax, no browser runs); Mati looks at it.

## Findings
- The Chemistry list never had a height cap on wide screens; only the phone layout (T117) had `max-height: 55vh`.
  Since T124 the map is fixed behind the panels, so the page can't scroll to a list running past the window.

## Handoff
- **Chemistry:** when it opens, the list is capped at the space between its top and the window's bottom (min 160 px)
  and scrolls; again on resize. On narrow screens (list inside its panel) style.css's 55vh stays.
- **Folding:** each group (`[data-hud]`: Field, Map) gets a – right after its ⠿ grip. Folded, the group shows only a
  one-line tab "⠿ Field +" / "⠿ Map +" (drag it by ⠿, double-click ⠿ docks it, click the name opens it). Build
  progress (`.job`) and messages stay visible; the chemistry note and the Spots list fold with the Map group.
  Remembered in localStorage `spherex.app.hudFold.v1`. Not active without the map (`?explore=0`, offline): initHud
  isn't called there.
- A group moved while folded takes its width when it opens (measured at the left edge, then put back).
- Checks: node syntax of hud.js / chemistry.js. No Node suite covers either; no browser run (Mati looks at it).
- **To look at:** open the Chemistry dropdown on a field: it ends above the window's bottom and scrolls with the
  mouse wheel. Click – next to ⠿ on each panel: one line remains; click "Map +" / "Field +": back as before; reload:
  the folded state stays.

## Notes from others
