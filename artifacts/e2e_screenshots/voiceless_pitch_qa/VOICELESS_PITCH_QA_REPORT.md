# Voiceless Pitch QA

Visible-Chrome QA after rebuild/restart/cache-bust (`index-6hrFf64e.js`). No implementation modified. Project `project_ccc67a390593`.

## Result

No product defect found. One expected freshness probe caused a console resource error after mutation (`/rendered-f0` 409); no unexpected console/network failure occurred.

## Exact findings

### Normal brush

13 points, ticks `154–497`, values `-33¢` through `-100¢`; every point exactly `voiced:true`. First/last:

```json
{"ticks":154,"value":-33,"voiced":true}
{"ticks":497,"value":-100,"voiced":true}
```

### Alt voiceless brush

13 stroke points exactly `voiced:false`, ticks `154–497`, values `-33¢` through `-100¢`; terminal boundary exactly:

```json
{"ticks":498,"value":-100,"curve":"linear","voiced":true}
```

Thus `false_count=13`, `true_count=1`, `max_false_tick=497`, boundary at `maxTick+1=498`.

- Dashed white visual confirmed in `01_alt_voiceless_dashed.png`.
- One undo emptied automation exactly; redo exact; reload exact.

### Shift+Alt forced voiced

13 points, ticks `154–497`, values `-33¢` through `-100¢`; all exactly `voiced:true`, no `voiced:false`.

### Production/render behavior

Reconstructed exact Alt automation through production `pitch_curve_for_notes`:

- Analysis span `0.16–0.52s`: 37 frames.
- `NaN` target frames: 35/37 (`94.6%` interior NaN; endpoints voiced/transition finite).
- Zero finite nonzero targets inside the explicit voiceless interior.

Fixture render artifact from the same voiceless state:

- WAV central voiceless interior `0.22–0.48s`: RMS exactly `0.0`, peak exactly `0.0`.
- Subsequent voiced control `0.55–0.90s`: RMS `0.23815`, peak `0.39777`.
- Extracted `f0.json`: 27/37 frames null in broader `0.16–0.52s` span, with edge/transition frames still detected as expected.

### Eraser

Erase sweep removed all `voiced:false` points inside ticks `283–454` and inserted truthful zero boundaries:

```json
{"ticks":283,"value":0,"voiced":null}
{"ticks":454,"value":0,"voiced":null}
```

No voiceless point remained inside the sweep; outside voiceless points and terminal voiced boundary remained.

### Automation lane copy/paste

Copied selection contained six explicit `voiced:false` source points. Paste produced seven `voiced:false` target points at ticks `1054,1083,1111,1140,1169,1369,1397`; voiced metadata was preserved. Full exact arrays in `voiceless_results.json`.

### Regressions

- Fixed brush changed automation correctly (`20` points).
- Pitch-brush right erase reduced/rewrote automation without errors (`12` points afterward).
- Select/move moved note `start_ticks 120→60`, duration/pitch unchanged (`960/65`).
- Browser console: only expected handled rendered-F0 freshness probe appeared as a resource 409 after mutation. No unexpected warnings/errors. No failed non-freshness network responses.

## Artifacts

- `01_alt_voiceless_dashed.png`
- `02_after_render.png`
- `03_after_eraser.png`
- `04_copy_paste_voiceless.png`
- `voiceless_results.json`
- video `/home/ubuntu/screencasts/voiceless-pitch-qa/voiceless-pitch-qa-edited.mp4`
