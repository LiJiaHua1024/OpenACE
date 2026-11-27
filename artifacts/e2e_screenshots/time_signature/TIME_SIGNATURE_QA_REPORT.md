# Time signature QA report

Date: 2026-11-27
Scope: editable time signatures in real visible Chrome at exact 1272×837, fixture backend.

## Verdict

All focused acceptance checks passed. No implementation defect was confirmed.

## Results

- New visible project started with transport time-signature select at `4/4`.
- Visible switch to `6/8` persisted immediately to backend `{numerator:6,denominator:8}`.
- Piano roll, arrangement, automation, and tempo lane grids visibly narrowed together; no duplicated/misaligned grids or overlap were visible.
- Quantitative pixel evidence at default zoom (`112 px/quarter`, ppq 480):
  - 4/4 bar width = 1920 ticks = 448 px; second bar line at screen x≈748.
  - 6/8 bar width = 1440 ticks = 336 px; second bar line at screen x≈636.
  - Mean vertical-line brightness reversed exactly across all four surfaces:

| surface | 4/4 x748/x636 | 6/8 x636/x748 |
|---|---:|---:|
| arrangement | 1.32× | 1.32× |
| tempo | 1.25× | 1.25× |
| piano | 1.74× | 1.74× |
| automation | 1.28× | 1.32× |

- Transport readout counted denominator-aware eighth-note beats:
  - tick 240 → `1.2.1`
  - tick 1440 → `2.1.1`
- After browser reload, select and backend remained `6/8`.
- Visible undo returned select/backend to `4/4`; visible redo restored `6/8`.
- Screenshot review found no overlap or obvious visual defect.
- No console errors. The only network failures were two expected `/api/events` `ERR_ABORTED` disconnects caused by deliberate page reload; no failed application API interaction occurred.

## Harness transparency

- I initially attempted undo after reload, but undo history is session-local and the button was correctly disabled. I then tested undo/redo before reload, which is the meaningful normal-session behavior.
- My first exact-RGB grid oracle was invalid because canvas backing-store downscaling and the red playhead alter exact pixels. The final brightness-ratio analysis uses clean columns x636/x748 and is stronger quantitative evidence.

## Evidence

- `time_signature_results.json` — machine-readable results and pixel metrics
- `01_default_4_4.png`
- `02_switched_6_8.png`
- `03_transport_tick1440_6_8.png`
- `04_reload_persisted_6_8.png`
- `05_undo_back_4_4.png`
- `06_redo_back_6_8.png`
