# XF badge focused recheck addendum

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837 against a backend restarted from the current working tree.

## Result

Focused recheck passed. No defect found.

- Fresh project using the same low/high fixture clips: `project_78f3e6fa1963`.
- A real visible-UI drag moved the second clip from `960` to `720` ticks, recreating the same `720–960` tick overlap.
- Bright-cyan crossfade pixels still span exactly the expected overlap region, canvas x `231–288`.
- Zoomed visual review shows the tiny `XF` badge at the overlap top-left.
- The `XF` badge no longer collides with the `B high` clip label; the badge is above the label with clear separation.
- The complementary X-shaped crossfade curves and shading remain understandable.
- No console errors occurred.

## Evidence

- `evidence_xf_badge_zoom.png` — zoomed badge/label/crossfade evidence.
- `xfade_badge_recheck_full.png` — full visible-browser screenshot.
- `xfade_badge_recheck_results.json` — machine-readable focused result.
