# Mixed Cantonese/English Browser QA

Date: 2026-11-28  
Project: `project_e84832b92141` (`Mixed Yue QA`)  
Backend: restarted current fixture backend on port 8787  
Frontend: rebuilt production bundle `index-B0D_yucG.js`, cache-busted in visible Chrome  
Implementation modified: no

## Verdict

Focused browser verification passed. No defects found.

## Evidence

- Four notes were created through visible piano-roll drag gestures: starts `[120,720,1320,1920]`, duration `360`, pitch `67`.
- `Mixed Cantonese/English` (`mixed-yue`) was visible and selectable in the language dropdown.
- Correct piano-roll `Lyrics…` batch editor accepted `我 hello 你 world` for exactly four notes.
- Backend notes/phonemes became exactly:

```text
我     -> ŋ ɔː
hello  -> h ə l oʊ
你     -> n ɛː i
world  -> w ɝ l d
```

- Supporting current-tree SoulX adapter inspection for the same phrase emitted:

```text
yue_ngo5
en_HH-AH0-L-OW1
yue_nei5
en_W-ER1-L-D
```

- Mixed fixture render completed: `job_140a03898172`, no error, explicit CI fixture.
- Mixed render output was valid PCM WAV: 69,000 frames at 24 kHz, exactly 2.875 seconds, 138,044 bytes.
- Direct WebAudio instrumentation observed the rendered vocal source scheduled with duration `2.874988662s`; transport advanced to `1.3.2 / 00:01.19` while playing.
- Pure Cantonese regression: language switched to `yue`; batch input `我 你 我 你` assigned exactly with phonemes `ŋ ɔː` and `n ɛː i` on alternating notes.
- Pure Cantonese fixture render completed: `job_c5cf17f9acfa`, no error, same valid 2.875-second output facts.
- Browser console errors/warnings: zero. Failed network responses: zero.

## Workflow note, not a defect

Immediately after drawing notes, the final note remains selected, so the batch editor correctly targets one selected note rather than all four. The test used Ctrl+A to select all notes before opening `Lyrics…`; the editor then targeted all four and applied successfully. The UI visibly explains this targeting behavior.

## Artifacts

- `mixed_yue_results.json`
- `soulx_token_supporting_evidence.json`
- `render_file_facts.json`
- `01_four_notes_drawn.png`
- `02_mixed_yue_batch_applied.png`
- `03_mixed_yue_render_completed.png`
- `04_mixed_yue_playback.png`
- `05_pure_cantonese_regression_render.png`
