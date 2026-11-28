# Compact Transport Retest Addendum

Date: 2026-11-28
Scope: focused re-verify of only the previously failing compact transport defect after moving the `@media (max-width:1350px)` block after the broader 1450px block.
Viewport: exactly `1280 × 841` CSS px.
Frontend: cache-busted production build `index-D4n9Fg4d.js`.
Implementation was not modified or committed.

## Result: passed

Exact measured state:

```text
innerWidth: 1280
transport header scrollWidth: 1280
transport header clientWidth: 1280
body scrollWidth: 1280
body clientWidth: 1280
```

Import-label measurements:

| label | visible pseudo-label | bounds | width | scrollWidth/clientWidth | inside viewport | internally unclipped |
|---|---|---|---:|---:|---|---|
| Import MIDI | `MIDI` | x `1135 → 1177` | 42 | `40/40` | yes | yes |
| Import USTX | `USTX` | x `1183 → 1225` | 42 | `40/40` | yes | yes |
| Import audio | `Audio` | x `1231 → 1273` | 42 | `40/40` | yes | yes |

Computed compact styles now correctly show `font-size: 0px`, `padding: 6px 0px`, and pseudo font size `10px`, so only the exact short pseudo-label is visible. The enlarged crop visually reads exactly `MIDI`, `USTX`, and `Audio`; there is no composite text such as the previous `MIDIm`/`USTXIr` fragments.

Clickability regression:

- MIDI opened a file chooser accepting `.mid,.midi`.
- USTX opened a file chooser accepting `.ustx,.zip`.
- Audio opened a file chooser accepting `audio/*,.wav,.mp3,.flac`.

Console/network: zero console errors, zero console warnings, zero page errors, zero failed network responses during the measured pass.

## New evidence

- `08_compact_transport_retest_1280.png`
- `09_compact_transport_retest_right_crop_x2.png`
- `compact_transport_retest_results.json`
- Recording: `/home/ubuntu/screencasts/compact-transport-retest/compact-transport-retest-edited.mp4`
