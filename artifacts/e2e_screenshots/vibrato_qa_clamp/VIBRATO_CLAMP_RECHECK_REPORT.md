# Vibrato popover clamp — focused revalidation

Visible Chrome was driven with Playwright/CDP at the same normal desktop viewport used in the original QA (screenshots 1272x837). The existing low C4 vibrato note was context-opened, measured, interacted with, closed, then reopened from the toolbar.

## Result

Focused revalidation passed. No remaining defect was found in this scoped recheck.

| Check | Result | Measurement |
|---|---|---|
| Low-note context-menu popover remains inside piano-roll wrap | PASS | editor `(x=374,y=370,w=218,h=253)`; wrap `(x=236,y=229,w=714,h=414)`; bottom 623 <= wrap bottom 643 |
| Popover no longer spills into automation lane | PASS | 20px margin remains above wrap bottom; visually clear of automation panel |
| Controls usable after clamping | PASS | all four sliders enabled; depth keyboard interaction reached max 120 then returned exactly to 80 |
| Toolbar placement remains normal | PASS | editor `(x=326,y=309,w=218,h=253)` inside same wrap |
| Console/network health | PASS | no browser console errors or network failures |

## Evidence

- `01_context_editor_clamped_low_note.png` — clamped context-menu editor, visually inside the piano-roll surface
- `02_toolbar_editor_placement.png` — toolbar-opened editor placement
- `vibrato_clamp_results.json` — measured geometry and control-state evidence
- `browser_console.jsonl` — console/network health log

Note: an initial harness interaction clicked the center of the depth slider and changed its value as native range input behavior; this was corrected through the visible slider keyboard interaction and final depth was restored to 80. This was test-harness behavior, not an application defect.
