# Arrangement fades fix — focused recheck

Visible Chrome 1272x837, Playwright/CDP, fixture project `project_e3f52a65d029`.

## Outcome

The two prior fade/trim defects are fixed, and gain can be stepped to -6 dB successfully. However, a new numeric-input usability defect remains: typing `-6` directly into Clip gain produces `06` and persists `+6.0` dB.

## Results

| Check | Result | Evidence |
|---|---|---|
| Visible inner fade endpoint drag | PASS | dragging visible endpoint changed `fade_in_ticks 240 -> 360`; clip start remained 0 and duration 2400 |
| Right trim exact restoration | PASS | inward `2400 -> 2280`; outward restored exactly `2400` |
| Clip gain menu visible | PASS | context menu shows `Clip gain` numeric input and dB label |
| Typing negative gain | FAIL | typing `-6` became input `06` and persisted `gain_db=+6.0`; the intermediate `-` appears to be coerced away before the digit |
| Stepping negative gain | PASS | ArrowDown steps reached input `-6` and persisted `gain_db=-6.0` |
| Console/network health | PASS | zero errors/failures |
| Cleanup | PASS | fixture project restored |

## Defect

### Negative values cannot be typed naturally into Clip gain

The controlled numeric input appears to parse the intermediate `-` as `NaN`/0 and immediately rerender, so typing `-6` results in `06` and positive 6dB. Users can work around with spinner/ArrowDown steps, but direct numeric entry is misleading and destructive because it persists the wrong sign.

## Artifacts

- `01_inner_fade_endpoint_drag_held.png`
- `02_inner_fade_endpoint_after.png`
- `03_right_trim_restored.png`
- `04_clip_gain_negative_typing_defect.png`
- `05_clip_gain_minus6_stepped.png`
- `fades_fix_results.json`
- `browser_console.jsonl`
