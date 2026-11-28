# Pitch Eraser Boundary-Fix Retest Addendum

Implementation was not modified. Rebuilt frontend (`index-BBJBY47J.js`) and restarted fixture backend. Retest used visible Chrome at `1272×837`, project `project_1afdcb6efa28`.

## Defect status

No defect reproduced. The previously reported zero-crossing boundary leak is fixed in this retest.

## Exact zero-crossing recheck

Setup: `-100¢ @ tick 0`, `+100¢ @ tick 400`; visible erase approximately `200 → 300`.

Resulting backend automation:

```text
-100¢ @ 0
   0¢ @ 200
   0¢ @ 300
+100¢ @ 400
```

Assertions passed:

- both boundary zero anchors inserted exactly at `200` and `300`
- interior samples at `200/225/250/275/300` all exactly `0¢`
- outside nonzero points exactly preserved
- readout `300 ticks · erased user pitch`
- undo restored exact seeded two-point envelope
- redo restored exact erased four-point envelope
- reload preserved exact erased envelope

## Regression results

- normal brush-seeded middle erase/backtracking passed: path `400 → 500 → 350 → 520`; anchors `350/520`; interior removed; outside exact; center interpolation `100¢ → 0¢`
- already-zero-span erase `[400,450]` added no redundant points (`17 → 17`, unchanged)
- blank erase remained pollution-free (`[]`)
- brush regression passed: wrote 8 points with readout `1500 ticks · -100¢ user pitch`; one undo returned exactly to empty automation
- 1272 layout passed with no overflow
- console/network clean; no backend HTTP 500/traceback lines observed

Artifacts: `pitch_eraser_fix_results.json`, `10_fix_zero_crossing_before.png`, `11_fix_zero_crossing_after.png`, `12_fix_normal_middle_erase.png`, `13_fix_final_layout.png`.

## Post-restart confirmation

The first attempted backend restart hit a stale-pid port bind error because the prior server was still listening; the new frontend bundle was nevertheless confirmed as served (`index-BBJBY47J.js`). The backend was then properly restarted with no startup errors, and the exact zero-crossing probe was repeated after that restart. It passed again with exact points `-100@0, 0@200, 0@300, +100@400` (`postrestart_zero_crossing_results.json`, `14_postrestart_zero_crossing.png`).
