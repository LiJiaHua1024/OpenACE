# Loop Playback Region Focused Browser QA

Date: 2026-11-27  
Surface: real visible Chrome through Playwright/CDP, exact CSS viewport `1272×837`  
Backend: restarted with `OPENACE_CI_SYNTH_FIXTURE=1` and fixture delay `0.2s`  
Frontend: rebuilt/cache-busted; implementation unchanged.

## Result

All 14 authoritative focused checks passed. Precise cycle measurement was performed after one automation-browser AudioContext/decode warmup click; instrumentation arrays were reset before measurement.

## Exact loop timing evidence

Dragged loop range: `0–480` ticks at `120 BPM` / `ppq=480`, i.e. `0.5s` musical span. Canvas band measured x `64`, width `112px`, exactly matching `480/480*112`.

AudioBufferSource start times (`AudioContext.currentTime` seconds):

`0.6966, 1.2074, 1.7067, 2.2175, 2.7167, 3.2160, 3.7152, 4.2144`

Cycle intervals:

`0.5108, 0.4992, 0.5108, 0.4992, 0.4992, 0.4992, 0.4992`

- Starts: `8` (therefore more than two complete loop cycles)
- Mean interval: `0.5025s`
- Population stdev: `0.0052s`
- Restart source offsets: `0.0108, 0.0101, 0.0209, 0.0201, 0.0194, 0.0186, 0.0178s`
- Playhead positions sampled ~56ms after restart: `0.06–0.07s`
- Interpretation: restarts are phase-correct within frame/scheduler overshoot and show no cumulative drift.

## Other verified behavior

- Loop button before any range created active default current-bar loop: canvas cyan band width `448px`, exactly one 4/4 bar (`1920 ticks`) at `112px/beat`.
- Keyboard `L` outside inputs toggled existing loop off/on; `loop off` label appeared when disabled.
- Plain ruler click still sought (`1.2.1`, `0.50s`) rather than creating a range.
- Ruler drag created the snapped enabled cyan `0–480` tick band.
- Loop toggle off allowed playback beyond old end: only one audio start, playhead reached `1.26s` / `1.3.3`.
- Pause preserved position (`1.40s` before/after waiting); Stop reset to `0.00s`.
- Post-loop ruler click seek remained correct.
- Alt-drag repaint region remained separate: repaint inputs `0.70–1.19s`; orange `repaint region` label coexisted with cyan `loop off` label.
- Nine-lane vertical scroll still worked (`scrollTop 0→127`); sticky ruler click seeked to `1.2.3` / `0.83s`.
- Layout exact: body `1272/1272`, transport `1272/1272`, arrangement `210px` viewport / `336px` content; no overflow.
- Console `0`; HTTP errors `0`; unexpected network failures `0`.

## Files

- Recording: `/home/ubuntu/screencasts/loop-playback-final/loop-playback-final-edited.mp4`
- Machine results: `loop_playback_results.json`
- Key screenshots: `00_default_current_bar_loop.png`, `01_dragged_half_beat_loop.png`, `02_after_loop_cycles.png`, `03_loop_off_beyond_end.png`, `04_alt_drag_repaint_separate.png`, `05_scrolled_sticky_ruler_loop.png`
