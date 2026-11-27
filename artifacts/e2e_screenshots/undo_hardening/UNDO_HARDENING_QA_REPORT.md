# Undo/redo hardening QA

## Verdict

**Two defects/caveats found; core drag/render/external-invalidation hardening passed in corrected valid runs.**

## Defects and caveats

1. **Lyric edits clear undo ancestry — defect.**
   - Rapid lyric edits committed to backend (`一/二/三`), but the undo button became disabled instead of exposing one coherent undo step.
   - Network/JSON inspection shows why: the local whole-project save intentionally sets the edited note's `phonemes` to `[]`, while the backend re-phonemizes it before publishing the save echo (`phonemes` length became 1 for lyric `五`).
   - Because phonemes are musical/user-visible semantic content but are not part of the client's remembered local signature, the SSE echo looks like an unknown external semantic edit and conservatively clears undo/redo.
   - This means ordinary lyric editing currently defeats the undo-hardening mechanism.

2. **Title edits create no undo step at all — caveat/defect depending intended scope.**
   - Typing `Conflict Save QA X → Conflict Save QA X Y` left undo disabled before and after.
   - `TransportBar` title changes are wired as transient (`true`), so this is not merely coalesced into few steps; it is not undoable.
   - If title was included only as an example of direct non-transient edits, the implementation does not currently treat it that way.

3. **Arrangement audio-clip drag was not tested.** The selected vocal fixture has zero arrangement clips. Note-group piano-roll drag and note pitch automation drag were tested instead.

4. An early setup accident interrupted the desktop/browser service with an overly broad process kill; VNC/Chrome were restored before valid testing. This did not affect repo code or final API/UI evidence.

## Valid corrected results

- **Rapid fader-style volume edits coalesce correctly:** passed.
  - Ten rapid ArrowLeft steps in 0.117s changed volume `0.99 → 0.89`.
  - One undo restored `0.99`; one redo restored `0.89`.
- **Continuous note drag transaction:** passed.
  - First note pitch `64 → 65`, start/duration unchanged (`0/480`).
  - One undo restored pitch `64`; one redo restored pitch `65` exactly.
- **Continuous pitch automation create+drag transaction:** passed.
  - Created exactly one pitch point `{offset_ms: 106, cents: 163}`.
  - One undo removed it; one redo restored the exact same point.
- **Render completion does not wipe functional undo history:** passed.
  - Volume edit `0.89 → 0.90`, then manual render job `job_bfd277503b98` completed.
  - After completion volume remained `0.90`, undo was still enabled, one undo restored `0.89`, redo restored `0.90`.
- **External/API semantic edit invalidates history conservatively:** passed.
  - Before external edit undo was enabled.
  - External whole-project API title edit to `External Invalidation QA` returned 200.
  - After SSE, title was visible and both undo/redo were disabled.
- **Save/reload persistence:** passed with caveat.
  - API after reload preserved title `External Invalidation QA` and lyrics `['五','二','三']`.
  - Because pinned projects boot first, browser reload initially opened `FolderQA Beta`; target was then explicitly reselected for supplemental testing.
- **Console/page/network errors:** none in initial or corrected instrumented runs.

## Invalidated first attempts

- One first volume attempt pressed ArrowRight while volume was already at max `1.0`, so it was not a valid edit test.
- One first note/pitch drag attempt used off-screen pitch coordinates before scrolling the piano-roll pitch range. These were superseded by corrected valid runs.

## Artifacts

- `undo_hardening_results.json`
- `02_lyric_undo_disabled_failure.png` — lyric undo disabled failure evidence
- `13_external_invalidated.png` — external invalidation evidence
- `15_volume_valid.png`
- `16_pitch_range_scrolled.png`
- `17_note_drag_valid.png`
- `18_pitch_drag_valid.png`
- `19_render_history_valid.png`
