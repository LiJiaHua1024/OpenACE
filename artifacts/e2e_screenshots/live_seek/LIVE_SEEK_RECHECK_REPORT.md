# Live seek recheck / verdict correction

The initial “forward-seek duplicate source” verdict is retracted. That run was measurement-contaminated: instrumentation was cleared before initial decode/scheduling had certainly completed, and horizontal scroll made the nominal target unreliable. It was not valid evidence of a duplicate seek scheduling defect.

## Exact arrangement identity inspection

The original live-seek harness used `project_76a53c5e0868` / “Loop Playback QA”: one rendered vocal track and no audio clips, so the two observed starts there were not two legitimate independent clips. However, those starts were explained by harness scheduling/decode contamination rather than proven implementation duplication.

The overlapping fixture identified during re-inspection is `project_d152f8c8ae7d` / “Automation Range Clipboard QA”:

- `sticky_2` / Sticky Lane 3 / clip `sticky_b2`: start `600`, offset `0`, duration `960`
- `sticky_3` / Sticky Lane 4 / clip `sticky_b3`: start `600`, offset `0`, duration `960`

These are independent clips on distinct tracks. In a forward seek to tick960, exactly two replacement starts occurred in one batch at identical source offset `0.3725997373343868`, and exactly two stops occurred. That behavior is legitimate.

## Controlled single-clip tempo-map proof

A controlled duplicate `project_05ddbf3d48f2` retained the complex tempo map but exactly one audio clip (`sticky_b2`, start600/offset0/duration960).

- Initial playback: exactly one source.
- Live forward seek tick960: exactly one replacement start, exactly one stop, source offset `0.3725997373343868s`, matching tempo-map arithmetic exactly.
- Live backward seek tick600: exactly one replacement start, exactly one stop, source offset `0`.
- Paused piano-ruler seek to tick600 then play: exactly one source at offset `0`.
- Clock agreement supplement after decode:
  - tick960 error `-0.01346s`
  - tick600 error `-0.01606s`
  both within the requested ~80ms.
- Console/network/HTTP clean.

No live-seek implementation defect confirmed in the corrected focused run.
