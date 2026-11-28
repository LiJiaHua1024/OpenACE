# Pitch Eraser QA — focused uncommitted verification

Implementation was not modified. Frontend was rebuilt (`index-BM1t-SeI.js`) and the fixture CPU backend was restarted. Visible Chrome QA used CSS viewport `1272×837` against project `project_1afdcb6efa28`.

## Defect found

### P1/P2 — zero-crossing edge leaks nonzero pitch through the erased span

Exact API-seeded setup, then visible eraser drag:

- seeded automation: `-100¢ @ tick 0`, `+100¢ @ tick 400`
- erased visibly from approximately tick `200` to `300`
- before erase, outside automation crosses exactly `0¢` at tick `200` and is nonzero through `(200,300)`
- actual result: only one zero boundary anchor was inserted, at tick `300`; no zero anchor at tick `200`
- resulting interpolation inside the supposedly erased span:
  - tick 200: `-33.33¢`
  - tick 225: `-25¢`
  - tick 250: `-16.67¢`
  - tick 275: `-8.33¢`
  - tick 300: `0¢`

This violates the intended boundary semantics: nonzero user pitch still interpolates through most of the erased span. The implementation decides whether to insert each boundary independently from the original outside envelope; inserting/removing the other boundary can change the interpolation at the first boundary. In crossing cases, both boundary anchors may be collectively necessary even when one endpoint originally evaluates to zero.

Evidence: `zero_crossing_edge_results.json`, `06_zero_crossing_before_erase.png`, `07_zero_crossing_after_erase.png`.

## Passing hard gates

- **Shortcut/tool activation:** passed — shortcut `2` activated `⌦ Pitch`.
- **Blank automation no-pollution:** passed — dragging eraser over empty automation left `pitch_cents` exactly `[]`; readout `520 ticks · erased user pitch`.
- **Seeded brush automation:** passed — brush wrote 17 exact sorted points across two notes.
- **Middle-range erase with expansion/backtracking:** passed — path `400 → 500 → 350 → 520`; final cumulative erased range was exactly represented by zero boundaries `350` and `520`.
- **Interior removal:** passed — all nonzero interior points in `[350,520]` removed.
- **Outside preservation:** passed — all outside automation points survived exactly.
- **Positive boundary semantics:** passed — interpolation at center was `100¢` before erase and `0¢` after erase.
- **Negative/zero-span boundary semantics:** passed — erasing `[400,450]` inside the already-zero span added no points and left all 16 points unchanged.
- **Undo/redo:** passed — one undo after erasing restored the seeded 17 points exactly; redo restored the erased 16 points exactly.
- **Reload persistence:** passed — post-erase automation matched exactly after reload; curve remained visible in eraser mode.
- **Readout:** passed — eraser readout examples `520 ticks · erased user pitch`, `450 ticks · erased user pitch`, `300 ticks · erased user pitch`.
- **Fixture render now consumes pitch automation:** passed — baseline/brush/erase WAV hashes all differed.
  - baseline SHA `8ef6df53…`
  - brushed SHA `cdd6f3a4…`
  - erased SHA `e7a5d500…`
- **Erased render moves toward baseline:** passed — mean absolute sample difference `brush vs base = 0.106641`, `erased vs base = 0.101907`, `erased vs brush = 0.026312`; erased audio is measurably closer to baseline while still correctly retaining outside automation.
- **Brush regression:** passed — post-eraser brush stroke changed automation and readout `1500 ticks · -100¢ user pitch`; one undo restored pre-brush automation exactly.
- **Anchor regression:** passed — per-note handle `{offset_ms:324, cents:150}` created without changing continuous automation.
- **Pencil regression:** passed — visible pencil created third note without changing automation.
- **Select regression:** passed — note move worked and undo restored it; automation unchanged.
- **Velocity regression:** passed — velocity changed `90 → 124`; automation unchanged.
- **1272 layout:** passed — no body/transport/right-panel overflow.
- **Console/network/backend:** passed — zero browser console errors/warnings, zero failed browser responses, no backend HTTP 500s/tracebacks.

## Harness note

The zero-crossing automation was seeded through the project API to create an exact adversarial control envelope; the eraser itself was then operated visibly in the browser. This is setup seeding, not a substitute for UI coverage of the tested erase gesture.
