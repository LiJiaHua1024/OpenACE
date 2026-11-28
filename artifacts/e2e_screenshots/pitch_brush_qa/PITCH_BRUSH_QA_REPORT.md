# Freehand User-Pitch Brush QA — focused uncommitted verification

Implementation was not modified. Frontend was rebuilt (`index-1TXX13gK.js`) and the fixture CPU backend was restarted. Browser QA used visible Chrome at CSS viewport `1272×837` against project `project_8a2b2f4d3cac`.

## Defects

No confirmed product defect found in the tested implementation.

Initial fixture caveat, subsequently fixed: during this browser QA the explicit CI fixture vocal synthesizer was note-only and did not pitch-shift its synthetic oscillator from `pitch_cents`, so the fixture WAV SHA-256 was identical before/after brushing. After QA, the fixture renderer was deepened to consume per-note handles, vibrato, and continuous pitch automation with phase-continuous instantaneous F0; focused regression now measures a +600-cent automation envelope moving the dominant oscillator frequency by approximately `sqrt(2)`. This fixture remains explicitly artificial CI audio and does not prove production-model timbre.

## Hard-gate results

- **Multiple notes and brush activation:** passed. Created sung notes at pitches `65` and `68`; shortcut `1` activated `🖌 Pitch` (`shortcut_active=true`).
- **Across-two-note exact stroke:** passed. Horizontal absolute-pitch-66 stroke produced exact note-relative values: note 65 `+100¢`, note 68 `-200¢`; backend points were sorted and unique.
- **Readout:** passed. First stroke readout ended at `1650 ticks · -200¢ user pitch`; second at `1380 ticks · -100¢ user pitch`.
- **One undo transaction / redo:** passed. After stroke 1, one Ctrl+Z removed the whole stroke (`[]`); Ctrl+Shift+Z restored all 17 points exactly.
- **Non-monotonic/backtracking rewrite:** passed. Stroke path ticks were `250 → 1380 → 580 → 1380`. Backend remained sorted/unique. Rewritten range inferred as `[250,1380]`; all 8 pre-existing points outside that range survived exactly; all 9 points inside were replaced with exact absolute-pitch-67-relative values (`+200¢` on note 65, `-100¢` on note 68); no old inside-range point remained.
- **Undo/redo across successive strokes:** passed. One undo after stroke 2 restored stroke 1 exactly; redo restored stroke 2 exactly.
- **Reload persistence:** passed. Reloaded project automation matched stroke 2 exactly, and the white user-pitch curve remained visible in brush mode.
- **White user-pitch curve:** passed visually. Screenshots show the light/white stepped curve following the stroke across both notes in brush and anchor modes.
- **Render input/fingerprint response:** passed. Baseline input fingerprint `4f2ba87c1a2708f7` changed to `91c0c0f70a648a2f`; final computed input fingerprint exactly matched track render fingerprint. Completed render job adopted the output.
- **Engine consumption proof:** passed. Calling the production SoulX target-F0 builder with persisted automation changed 51/101 target frames versus no automation (examples: frame 6 `403.5Hz` vs `380.8Hz`; frame 83 `370.0Hz` vs `415.3Hz`). The after-render diagnostic visibly plots the stepped target F0.
- **Fixture audio response:** initially limited because the old fixture synthesizer consumed only written note pitch. This gap was fixed after browser QA: the fixture renderer now consumes pitch envelopes and a focused measurable-frequency regression passes.
- **Anchor regression:** passed. `∿ Anchor` created/dragged exact per-note handle `{offset_ms:324, cents:150}` while continuous `pitch_cents` stayed unchanged; white user curve remained visible in anchor mode.
- **Pencil regression:** passed after correcting an initial harness coordinate that landed in the velocity lane. Visible pencil tool created a third note (`2100 ticks`, duration `420`, pitch `68`, lyric `啦`) and automation stayed unchanged.
- **Select regression:** passed. Select/move changed note 1 `(120,pitch65) → (240,pitch64)` without changing automation; undo restored it.
- **Velocity regression:** passed. Velocity drag changed `90 → 124`; automation stayed unchanged.
- **1272 layout:** passed. No document body overflow, transport overflow, or right-panel overflow.
- **Console/network/backend:** passed. Zero console errors/warnings, zero failed browser responses, and no backend HTTP 500/traceback lines observed.

## Harness note

The first pencil regression probe used a coordinate inside the velocity lane, so no note was created. The corrected visible-toolbar probe inside the note grid created the note successfully. This was a harness coordinate mistake, not a product failure.

## Key evidence

- `02_after_stroke1_white_curve.png` — first cross-note stroke and white curve
- `03_after_backtracking_stroke.png` — non-monotonic/backtracking rewrite and white curve
- `04_reloaded_white_curve.png` — persistence after reload
- `05_diagnostic_before_brush.png` / `06_diagnostic_after_brush.png` — diagnostic target-F0 response
- `07_anchor_mode_white_curve_and_handle.png` — anchor regression with user-pitch curve
- `09_final_three_notes_layout.png` — final three-note layout after pencil/select/velocity regression
