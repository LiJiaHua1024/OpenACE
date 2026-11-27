# Track Volume/Pan Automation QA

Visible Chrome validation on branch `devin/1795696369-dynamic-expression` after backend restart and cache-busted production frontend. Test project `Mix Automation QA` used a completed CI-fixture vocal render with three notes. Repo implementation was not modified.

## Editing and persistence

- **Volume/Pan tabs visible:** passed. Both appear in the automation surface next to existing expression lanes; Brush/Line/Erase tools are available.
- **Line editing:** passed.
  - Volume endpoints persisted at tick `0 = 0.8018018`, tick `960 = 0.1981982` (clear downward fade).
  - Pan endpoints persisted at tick `0 = -0.6793946`, tick `960 = 0.9717922` (clear left-to-right sweep).
- **Undo/redo:** passed. One undo removed the pan line, a second removed the volume line; two redos restored exact endpoint values.
- **Reload persistence:** passed. Both exact point pairs survived reload and were visibly redrawn. Undo history itself did not survive reload (`undo_enabled_after_reload=false`), which appears consistent with existing in-memory history behavior rather than a new defect.
- **Dense brush coalescing:** passed. A rapid dense brush drag wrote 35 points; one undo restored the prior exact 2-point volume line.

## Playback

Playback was instrumented read-only at WebAudio level. A clean first run captured 33 scheduled events per mix lane:

- Gain sequence: `0.8018018 → 0.1981982` over the rendered region.
- Pan sequence: `-0.6793946 → +0.9717922` over the same region.

A second run used a read-only ScriptProcessor tap at the master input. Results:

- Transport advanced normally (`00:01.13` while playing); no scheduling silence or stuck playhead.
- Total stereo energy dropped `2.69×` from early to late fade windows.
- Initial captured audio was left-dominant (first-block L/R RMS ratio about `3.7`).
- Late captured audio was right-dominant: R/L RMS ratio `4.17×`.
- Early/mid/late mean RMS evidence:
  - early L/R `0.14156 / 0.07785`
  - mid L/R `0.05002 / 0.06212`
  - late L/R `0.01574 / 0.06572`
- The loudness meter became available and showed playback history; no console/page/network errors occurred.

Note: an initial AnalyserNode byte-meter probe was too coarse/quantized for this low-level signal and produced a misleading intermediate threshold failure. It was superseded by the direct stereo ScriptProcessor capture above; this was a test-method limitation, not a product failure.

## Render staleness

Passed. After adding only volume/pan mix automation:

- no stale render badge appeared in the track card;
- `render_fingerprint` remained `3e449c332f6747ee`;
- backend canonical input hash remained `3e449c332f6747ee`;
- fingerprint/hash equality confirms mix automation is correctly excluded from vocal-render input identity.

## Export

Passed. Clicking the UI `STEMS` button downloaded `mix_automation_stems.zip` (`384,877` bytes) containing `stems_manifest.json` and non-silent `01_Mix_Vocal.wav` (2.0 s). Channel RMS showed the same fade/pan shape as playback:

- early L/R `0.14160 / 0.07870`
- late L/R `0.02303 / 0.07290`

## Defects

No implementation defect found in this focused pass.

## Artifacts

- `undo_reload_results.json`
- `dense_brush_results.json`
- `playback_results.json`
- `playback_capture_results.json`
- `export_results.json`
- `mix_automation_stems.zip`
- screenshots `00`–`14` in this directory
