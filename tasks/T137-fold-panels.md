# T137: Chemistry list scrolls; floating panels fold

- **Owner:** Mati  ·  **Status:** doing
- **Branch:** `mati/T137-fold-panels`
- **Depends on / feeds:** T124 (floating panels, Jonathan), T93/T127 (chemistry list)

## Goal
1. The Chemistry dropdown never runs past the bottom of the window: it is capped at the space below its button and
   scrolls (on wide screens it had no cap since the T124 floating UI; the T127 presets made it longer).
2. Each floating panel group (Field, Map) can be folded to one line: a – button next to its ⠿ grip; folded it shows
   ⠿ + its name, a click opens it again. Remembered per browser. Status (build progress, messages) stays visible.

## Plan
- [ ] chemistry.js: cap the open list to the window (on open and on resize); style.css: overflow-y auto.
- [ ] hud.js: fold button by the grip, folded tab (grip + name), remembered in localStorage; style.css rules.
- [ ] Light checks only (node syntax, no browser runs); Mati looks at it.

## Findings

## Handoff
Pending.

## Notes from others
