# Arrangement Clip Slip Editing QA

## Scope

Visible Chrome/Playwright validation of Shift+drag slip editing on a real decoded fixture waveform clip (`clip_slip_test`, 2.0 s WAV, clip duration 960 ticks at 120 BPM / PPQ 480). Repo code was not modified. Frontend was rebuilt/cache-busted and the backend restarted before testing.

## Result

All requested focused checks passed. No defect found.

## Assertions

- **Normal clip drag remains a move:** passed. `start_ticks` changed `0 → 120`; `duration_ticks` stayed `960`; `offset_ticks` stayed `0`. Undo restored `start_ticks=0`.
- **Edge trim remains unchanged:** passed. Right-edge trim changed `duration_ticks 960 → 840`; `start_ticks`/`offset_ticks` remained `0`. Undo restored `duration_ticks=960`.
- **Shift+drag right performs slip:** passed. `offset_ticks` changed `0 → 240`; `start_ticks` remained `0` and `duration_ticks` remained `960`.
- **Whole slip is one undo/redo transaction:** passed. One undo restored `offset_ticks=0`; one redo restored exactly `offset_ticks=240`.
- **Waveform phase visibly shifts:** passed. Before/after crop comparison shows the waveform envelope translating inside fixed clip boundaries (`05_waveform_phase_comparison.png`).
- **Playback uses slipped source offset:** passed. Instrumented `AudioBufferSourceNode.start` captured the clip source with `offset=0.25` and `duration=1`. At 120 BPM/PPQ 480, 240 ticks is exactly 0.25 s (960 ticks/sec). The additional zero-offset 2 s source is the separate rendered vocal playback source.
- **Left clamp:** passed. Shift+drag left from `offset_ticks=240` clamped exactly to `0`; boundaries remained `start_ticks=0`, `duration_ticks=960`.
- **Right/source-end clamp:** passed. A deliberately huge Shift+drag right clamped exactly to `960`. The source WAV is 2.0 s = 1920 ticks at this tempo; `1920 - 960` clip duration = exact maximum `960`.
- **Save/reload persistence:** passed. After reload, backend/UI-loaded clip state retained `start_ticks=0`, `duration_ticks=960`, `offset_ticks=960`.
- **Multi-selection regression:** passed. With two clips selected, Shift+drag did not slip; both clips moved by `+120` ticks while both offsets remained unchanged. One undo restored both original starts.
- **Console/page/network health:** passed. No console errors, page errors, or failed network requests observed during the instrumented run.

## Caveats

- Playback was verified through instrumentation of `AudioBufferSourceNode.start`, not by perceptual audio analysis.
- The fixture WAV is only 2.0 s, so the tested right clamp is 960 ticks; this is mathematically correct for the fixture.

## Artifacts

- `clip_slip_results.json`
- `00_clip_loaded.png`
- `01_before_slip.png`
- `02_after_slip_right.png`
- `03_clamped_slip.png`
- `04_multiselection_shift_drag.png`
- `05_waveform_phase_comparison.png`
