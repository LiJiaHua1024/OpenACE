# Karaoke Typography / Scene QA

Date: 2026-11-28  
Build: `index-F6zjEFqI.js`; backend restarted.  
Implementation modified: no.

## Defect-first verdict

No product defect found in this focused pass.

## Controls and persistence

Passed at exactly `1272×837`:

- 16 karaoke style controls visible in two columns
- no document/body overflow
- zero right-panel elements overflowing the viewport
- edited controls included lyric font, font size, lane spacing, colors, position, outline, shadow, letter spacing, lane font step, theme, effect, bold, motion, title, and brand

Distinctive persisted values after reload:

- font `Odd, Font ☃`
- font size `72`
- lane spacing `88`
- position `top`
- outline `7`
- shadow `4`
- letter spacing `6`
- lane font step `9`
- theme `forest`
- effect `texture`
- bold/motion/title/brand all `false`

Backend metadata matched these values exactly before reload; visible control values matched after reload.

Evidence: `01_karaoke_controls_1272.png`, `02_karaoke_controls_edited.png`, `03_karaoke_controls_reloaded.png`, `karaoke_typography_results.json`.

## MP4 export and unusual font robustness

Passed. Browser MP4 exports succeeded for all three scene paths:

| case | bytes | duration | streams |
|---|---:|---:|---|
| top + animated texture | 122676 | 3.067s | h264 + aac |
| center + studio grid | 129296 | 3.067s | h264 + aac |
| bottom + clean gradient | 78711 | 3.067s | h264 + aac |

The unusual font text `Odd, Font ☃` did not break export. Backend ASS sanitized the comma while preserving the unusual family text as `Odd Font ☃`.

Evidence: `karaoke_top_texture.mp4`, `karaoke_center_grid.mp4`, `karaoke_bottom_clean.mp4`, `mp4_stream_analysis.json`.

## ASS typography evidence

Passed. ASS lyric style contained exact exported typography:

- font `Odd Font ☃`
- font size `72`
- bold `0`
- spacing `6`
- outline `7`
- shadow `4`
- colors matching the edited sung/unsung values in ASS BGR representation

Position alignments were exactly:

- top: ASS alignment `8`
- center: ASS alignment `5`
- bottom: ASS alignment `2`

Evidence: `karaoke_top_texture.ass`, `karaoke_center_grid.ass`, `karaoke_bottom_clean.ass`, `ass_style_analysis.json`.

## Burned-frame proof

Passed visually and quantitatively. Extracted frames at `0.55s` show the lyric actually moving:

- top texture lyric centroid y ≈ `134`
- center grid lyric centroid y ≈ `542`
- bottom clean lyric centroid y ≈ `950`

The frames visibly show animated texture/noise, studio grid lines, and clean gradient respectively; grid/texture files are also larger because of their increased frame complexity.

Evidence: `frame_top_texture.png`, `frame_center_grid.png`, `frame_bottom_clean.png`, `frame_analysis.json`.

## Lane font step / lane spacing proof

Passed using an additional overlapping vocal lane added through the real MCP atom, then exported through CLI MP4:

- lane 0 font size `72`, marginV `96`
- lane 1 font size `63`, marginV `184`

This exactly proves lane font step `9` and lane spacing `88` are written into ASS rather than dead controls. The extracted frame shows two simultaneous lanes with different sizes/positions.

CLI MP4: exit `0`, `86315` bytes, valid `ftyp`, duration `3.067s`.

Evidence: `karaoke_lane_step_proof.mp4`, `karaoke_lane_step_proof.ass`, `frame_lane_step_proof.png`, `lane_step_proof.json`.

## Health

- browser console errors/warnings: zero
- failed browser network responses: zero
- backend HTTP 500s: zero
- backend tracebacks: zero

## Harness note

The first lane-proof MCP helper script itself had a Python harness bug after successfully adding the note (`list` object has no `get`). The project mutation was verified directly, then the CLI export/analysis completed separately. This was not a product defect.
