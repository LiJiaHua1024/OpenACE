# SVC Editable-Score Extraction Browser QA

Date: 2026-11-28  
Project: `project_5bf625fb46bb` (`SVC Editable Score QA`)  
Backend: restarted current fixture backend on port 8787  
Frontend: existing current production build in visible Chrome  
Implementation modified: no

## Verdict

The new editable-score extraction flow passed in the real browser path. No feature defect was confirmed.

## Quantitative evidence

### Clip-aware SVC and extraction

- Controlled speech-like source imported as arrangement clip `clip_875f53fa87c0`.
- The clip was dragged through the arrangement UI from zero to nonzero `start_ticks=480` (0.5s at 120 BPM); duration `2880`, offset `0`.
- Clip-aware SVC job `job_3128a198b3c6` completed with:
  - exact `clip_id=clip_875f53fa87c0`
  - source interval `0.0–3.0s`
  - `arrangement_start_ticks=480`
- Provenance was explicit and successful:
  - `editable_track_id=track_840432d59d5e`
  - `editable_note_count=3`
  - `editable_score_error=null`
  - `lyric_language=en`
  - `lyric_word_count=1`
  - `lyric_transcription_error=null`

### Editable score track

An `SVC score — …` vocal track appeared without reload. Backend facts before editing:

```text
note 1: start 480, duration 941, pitch 45, lyric You, 13 pitch-curve points
note 2: start 1478, duration 893, pitch 57, no lyric, 2 pitch-curve points
note 3: start 2410, duration 960, pitch 64, no lyric, 3 pitch-curve points
```

Thus the first extracted onset is exactly shifted to the source clip start (`480`), not zero. The track language was `en` and its reference voice was exactly the conversion reference:

```text
/home/ubuntu/repos/OpenACE/data/voices/voice_328da1a4cb92_svc_reference_voice.wav
```

Only one truthful ASR word (`You`) was present; the other notes correctly remained empty rather than receiving fabricated lyrics. After the first manual render, the lyric note had coherent phonemes `j u`.

The first extracted note is low (`A#2` after transpose), so it is outside the default piano-roll pitch viewport. Shift+wheel vertical pitch scrolling revealed it; screenshot `11_editable_score_low_notes_lyrics_visible.png` visibly shows the editable `You` note and phonemes.

### Edit → stale → manual render

- Initial manual fixture render of the extracted track completed: `job_309412a1e7da`.
- Visible transpose `+1` edited all extracted pitches `[45,57,64] → [46,58,65]`.
- Track card then visibly showed `STALE RENDER`; the stale warning panel appeared.
- Manual post-edit fixture render completed: `job_59433a996584`.
- Editable render files were valid 24 kHz WAV, exactly `4.0104167s`.

### Static SVC clip/correction lane regression

- Static conversion track `SVC — …` remained present with one clip.
- Static clip remained aligned at `start_ticks=480`, duration `2880`.
- Static clip retained truthful ASR word `You` at `0.0–1.42s`.
- Clicking the static arrangement clip opened the `SVC clip lyrics` correction lane with one editable row; no crash.
- Static conversion WAV was valid 24 kHz PCM, exactly `3.0s`.

### Playback/persistence

After reload, project state persisted and direct `AudioBufferSourceNode.start` instrumentation recorded three sources:

- editable vocal render scheduled at approximately zero
- imported source and static SVC clips scheduled at the nonzero 0.5s arrangement position

Transport advanced from `00:00.00` to `00:01.79` while playing. A second consecutive playback in the same reloaded page also advanced from `00:01.83` to `00:03.03`.

## Caveats / harness notes

- The first QA script mistakenly tried to select the editable track by visible title text; track titles are inputs and are not part of `.track-card.innerText`, so the click did not happen. This was a harness issue, not a product defect. Selecting the correct card index showed the editable voice panel and enabled `Render vocal` immediately.
- One pre-reload playback measurement in the long-lived test page did not advance despite scheduled sources. After reload, playback advanced correctly and a second consecutive playback also advanced. I do not count this as a new SVC feature defect, but it is an unexplained session-state anomaly worth watching in broader playback QA.
- Console/network error capture is strongest for the post-conversion edit/render/correction/playback phase: zero errors/warnings/failed responses there. No visible error or backend failure occurred during conversion.

## Artifacts

- `svc_editable_score_results.json`
- `render_file_facts.json`
- `playback_recheck.json`
- `01_source_clip_drag_held.png`
- `02_source_clip_offset_before_svc.png`
- `03_svc_completed_editable_score_visible.png`
- `04_editable_score_piano_roll.png`
- `05_editable_score_initial_render.png`
- `06_editable_score_transposed_stale.png`
- `07_editable_score_postedit_render.png`
- `08_static_svc_correction_lane.png`
- `09_playback_clean.png`
- `10_reloaded_playback_recheck.png`
- `11_editable_score_low_notes_lyrics_visible.png`
