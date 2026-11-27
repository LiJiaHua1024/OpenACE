# Cross-track ripple QA — incomplete/red flags

Real Chrome 1272x837, backend JSON verification. Implementation unchanged.

Confirmed single right-click ripple across tracks:
- selected `a_sel1` removed
- downstream audio clip `a_after` shifted `2400→1920` exact 480
- unselected downstream BGM selected fixture clip `b_sel2` shifted `1440→960` exact 480
- BGM downstream `b_after` shifted `2880→2400`
- earlier/overlapping `a_early`/`a_overlap` unchanged
- vocal notes/breaths/automation at/after interval end shifted exact 480; inside material unchanged
- undo restored canonical exactly
- playback entered playing state
- console/network clean

Defect: arrangement context menu measured not fully contained (`inside=false`, size 204x156). Need exact geometry follow-up.

Incomplete/red flag: redo via Ctrl+Shift+Z did not match single ripple, so redo/reload persistence could not be confirmed. Multi-select test did not actually select the second clip (BGM `b_sel2` remained), likely harness/selection-gesture issue; merged multi interval behavior therefore remains untested. Reload comparison inherited the failed redo state and is not meaningful.

Artifacts: screenshots/JSON/log in this directory.
