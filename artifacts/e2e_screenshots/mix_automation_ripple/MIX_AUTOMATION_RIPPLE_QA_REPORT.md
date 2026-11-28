# Mix Automation Ripple QA

Focused browser test passed. Backend restarted; implementation untouched.

- Direct automation dragging persisted interior points exactly at tick `1800`: volume `0.7000001099732545`, pan `0.3999996808619281`.
- Alt-drag selected exact range `1680–2160` (ripple length `480`) and context-menu `Ripple delete time range` succeeded.
- Interior volume/pan points at `1800` were removed.
- Correct interpolated boundary anchors inserted at `1680`:
  - volume `0.8200000439893018` (60% interpolation from 1800→2400)
  - pan `0.6399998723447713` (same interpolation)
- Downstream points shifted exactly once by `480`: `2400 → 1920`; before-range points at `480/960` preserved exactly.
- Undo restored original interior-point curves; redo restored exact ripple result; reload persisted exact ripple result.
- Brief playback regression started without crash.
- Console and network clean.

Test-process note: the first expectation in the test script mistakenly treated boundary interpolation as 50%; exact tick math is 60% (`(2160-1800)/(2400-1800)`), and backend output matches that correct value.

Evidence: `mix_automation_ripple_results.json`, `00_authored_volume_pan.png`, `01_range_selected.png`, `02_after_ripple.png`, `03_after_reload.png`.
