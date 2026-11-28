# Transport / Stale-badge / Repaint-provenance Focused Regression QA

Date: 2026-11-28
Backend: restarted in explicit fixture mode after the uncommitted fixes.
Frontend: cache-busted production bundle `index-KjlzO6mR.js` in visible Chrome.
Viewport: exactly `1280 × 841` CSS px.
Project reused: `project_9295440b4e47` / `Creative Loop 验收`.
Implementation was not modified or committed.

## Result summary

- Non-vocal stale-badge fix: **passed**.
- Vocal stale-badge behavior: **passed**.
- Repaint provenance fix: **passed end-to-end**.
- Compact transport fix at exactly 1280 px: **failed** — clipping and unreadable labels remain, although all three import controls are clickable.

## Defect

### P2 — compact transport still overflows and import labels are visually corrupted/clipped at exactly 1280 px

Exact DOM measurements at `innerWidth=1280`:

| control | left | right | width | internal scrollWidth | clientWidth |
|---|---:|---:|---:|---:|---:|
| MIDI import label | 1145.3046875 | 1187.3046875 | 42 | 96 | 40 |
| USTX import label | 1195.3046875 | 1237.3046875 | 42 | 108 | 40 |
| Audio import label | 1245.3046875 | **1287.3046875** | 42 | 107 | 40 |

The transport header itself reports `scrollWidth=1287` vs `clientWidth=1280`; Audio therefore extends **7.3 px beyond the viewport**. No pair of adjacent controls overlaps, but Audio is externally clipped.

The compact labels are also internally unreadable/corrupted. Computed style shows `font-size: 11px`, `padding: 6px 7px`, while the compact `::before` content is also present (`"MIDI"`, `"USTX"`, `"Audio"`). Visually the labels render as fragments resembling `MIDIm`, `USTXIr`, and clipped `Audio` in `01_transport_right_crop_x2.png`. The likely cascade issue is that the later `@media (max-width: 1450px)` rule overrides the compact font/padding declarations from `@media (max-width: 1350px)` while the compact width/pseudo-content still apply.

Clickability: all three controls did open file choosers in Playwright with correct accept values:

- MIDI: `.mid,.midi`
- USTX: `.ustx,.zip`
- Audio: `audio/*,.wav,.mp3,.flac`

Thus this is a layout/readability defect, not a dead-control defect.

## Passing assertions

### Generated non-vocal tracks do not show stale badges

Before mutation, track-card state was exactly:

- Lead Vocal: `stale=false`
- ACE-Step BGM / accompaniment / `render_path` present / fingerprint null: `stale=false`
- SVC audio / `render_path` present / fingerprint null: `stale=false`

### Vocal tracks retain stale-render behavior

After clicking the visible vocal `+12` transpose control:

- Lead Vocal displayed `STALE RENDER`.
- ACE-Step BGM remained clean.
- SVC remained clean.

After clicking `-12` and allowing save/fingerprint normalization, the Lead Vocal badge cleared again. This confirms the vocal stale path still responds to real note mutation and exact restoration.

### Repaint provenance is now correct end-to-end

A new fixture repaint was triggered through the visible UI after uploading/selecting a source again.

Before repaint:

```json
{
  "id": "clip_2f4bc04bee23",
  "path": ".../job_5a6b3f6fc9bf/accompaniment.wav",
  "created_by_job_id": "job_b10625e0c4ff",
  "updated_by_job_id": null
}
```

The repaint job completed as `job_51e7c291aa9d` with output `.../job_51e7c291aa9d/accompaniment.wav`.

After repaint:

```json
{
  "id": "clip_2f4bc04bee23",
  "path": ".../job_51e7c291aa9d/accompaniment.wav",
  "created_by_job_id": "job_b10625e0c4ff",
  "updated_by_job_id": "job_51e7c291aa9d"
}
```

This exactly proves original creation provenance is preserved and current repaint/update provenance is recorded.

### Console/network

No console errors, console warnings, page errors, or failed network responses were observed in the instrumented clickability, stale-badge, or repaint-provenance passes.

## Harness note

The first repaint-provenance attempt could not click `Repaint selection` because the button was legitimately disabled: `sourceAudio` is ephemeral React state and was empty after reloading the app. Re-uploading/selecting the source through the visible upload control enabled the button. This is a state/setup observation, not counted as a defect in this focused regression.

## Evidence files

- `00_transport_compact_1280.png` — full transport at exactly 1280 px
- `01_transport_right_crop_x2.png` — enlarged crop showing corrupted/clipped compact labels
- `02_import_click_targets.png` — state after file-picker clickability probes
- `03_stale_badges_before_mutation.png` — no stale badges before mutation
- `04_real_vocal_stale_after_plus12.png` — vocal-only stale badge after +12 transpose
- `05_stale_badges_after_restore.png` — badge cleared after exact -12 restoration
- `06_repaint_provenance_after.png` — arrangement/UI after repaint provenance test
- `07_final_state.png` — final state
- `transport_measurements_raw.json`
- `import_click_results.json`
- `stale_badge_results.json`
- `repaint_provenance_results.json`
