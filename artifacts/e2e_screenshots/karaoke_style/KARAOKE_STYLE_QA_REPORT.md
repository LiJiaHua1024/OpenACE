# Karaoke video style QA

Real Chrome exact 1272x837; implementation unchanged.

Passed:
- Controls visible/layout clean inside right panel (`00_controls.png`).
- Boundary inputs font_size `120`, lane_spacing `10` persisted raw in project metadata; backend exporter clamped font size to exact `96` in ASS. Lane spacing clamp logic is present, but this fixture produced only one lyric lane, so lane-spacing visual/ASS effect remains untested.
- Native-setter scripted color input events persisted exact `#ff0000`/`#00ff00`; burned frame truthfully shows first sung red glyph and second unsung green glyph.
- Ember + title/brand off frame: red/black background, no title/brand (`frame_ember_off.png`).
- Forest + title/brand on frame: green background, visible `Velocity Render QA` title and `OPENACE` brand (`frame_forest_on_0p7.png`).
- ASS exact final style: Lyrics fontsize `96`, sung `&H000000FF` (red), unsung `&H0000FF00` (green); conditional Title/Brand Dialogue events present in on export.
- Motion proof quantitative: off mean background diff `0.0028125`; on mean diff `5.59875`.
- Undo/redo are granular per edit; one Ctrl+Z undid the most recent single field and Ctrl+Y restored it exactly. Reload persisted exact metadata.
- Correct MP4/WAV downloads: MP4 51811/296047 bytes for two styles, WAV 720044 bytes.
- No console/network errors in corrected run.

Harness correction: first export accidentally targeted default first project after reload because the harness did not reselect the test project; those tiny artifacts were deleted and replaced by correct evidence.

Defects: none confirmed. Caveat: multi-lane lane_spacing behavior remains untested.
