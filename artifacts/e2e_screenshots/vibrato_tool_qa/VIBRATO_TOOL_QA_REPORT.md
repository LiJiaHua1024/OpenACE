# Vibrato tool QA

Implementation untouched. Rebuilt/restarted `index-EGUZsx3I.js`.

## Defect

P1/P2 transactional defect: after direct vibrato creation, the transport Undo button remains disabled and Ctrl+Z does not remove the vibrato. Code inspection confirms `onPointerUp` never calls `props.endTransaction()` for `vibratoGestureRef`, unlike pitch/fixed/eraser strokes. Thus the creation mutation is not committed as an undo transaction. Persistence still occurs, making this especially dangerous: the change is real but not undoable.

## Passing evidence

- shortcut 4 activates `∿ Vib`
- create right-to-left exact: start_ratio `0.25` (expected 0.25), depth `45¢` after 30px vertical distance, frequency `5.2`, phase `0`; note stayed `120/480/pitch65`
- reload persistence exact
- handles with vibrato tool active:
  - depth `45 → 75¢` after 20px upward drag
  - phase `0 → 1.0` after 40px horizontal drag
  - frequency `5.2 → 6.2Hz` after 30px horizontal drag
  - note remained exactly `120/480/pitch65`
- sine visualization visibly updates in `03_correct_handles.png`
- brush wrote automation and undo cleared it; eraser blank gesture did not pollute automation

## Caveats

Initial handle attempt was invalid because the harness did not reactivate vibrato mode after reload; corrected test above is the valid one. Console contained one rendered-F0 409 from a stale prior project before the new project was created; no later app errors were observed.

Artifacts: `vibrato_tool_results.json`, `vibrato_corrected_results.json`, screenshots, recording `/home/ubuntu/screencasts/vibrato-tool-qa/vibrato-tool-qa-edited.mp4`.
