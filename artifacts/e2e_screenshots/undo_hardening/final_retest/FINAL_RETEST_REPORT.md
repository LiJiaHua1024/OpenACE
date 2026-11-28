# Final undo hardening retest

Passed. Rapid title/lyric/volume edits coalesced correctly; distinct quick volume+BPM operations remained separately undoable; note drag and render-completion history preservation passed. Console/page/network clean.

Key exact results:
- title `External Invalidation QAABC` ↔ `External Invalidation QAABCABC` undo/redo exact
- lyrics `['六','七','八'] → ['甲','乙','丙']`, undo/redo exact
- rapid volume `0.91 → 0.90` after ten arrows in prior valid matrix pattern; distinct volume/BPM operations separately undoable
- note `[0,480,66] → [0,480,67]`, undo/redo exact
- render completed; volume edit `0.91 → 0.92` remained undo/redo exact
- rapid volume arrows exact: see `volume_coalesce_final` in JSON and `25_final_volume.png`
