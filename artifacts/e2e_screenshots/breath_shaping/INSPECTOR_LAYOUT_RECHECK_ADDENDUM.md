# Breath inspector layout recheck addendum

Date: 2026-11-27
Scope: targeted regression for the compact absolute-overlay inspector fix at 1272×837.

## Result

Passed.

## Checks

- Selected breath showed compact inspector inside the automation canvas.
- Geometry: inspector `x=684.7,y=689,w=257.3,h=28`; canvas `x=236,y=684,w=714,h=153`, so inspector is fully inside.
- Horizontal overlap with the selected breath body: `0px` in the tested layout; it does not meaningfully cover the breath body.
- **Add all breaths** remained visible in the unchanged header and was clicked by a real mouse hit with no DOM dispatch.
- Add-all created default breath `(start=1680,duration=120,intensity=1.0,timbre=natural)`.
- Slider drag persisted `intensity=1.5`.
- Timbre select persisted `strong`.
- No console errors.

## Evidence

- `layout_recheck_selected_inspector.png`
- `layout_recheck_add_all_real_click.png`
- `layout_recheck_final_strong.png`
- `layout_recheck_results.json`
