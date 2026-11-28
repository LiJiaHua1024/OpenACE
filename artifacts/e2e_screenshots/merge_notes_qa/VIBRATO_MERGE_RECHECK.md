# Vibrato Merge Recheck

Implementation modified: no. Backend restarted.

## Defect found

**P1/P2 edge defect:** split continuation pieces originating from one vibrato span with nonzero phase are rejected as inconsistent.

Setup vibrato: `start_ratio=0.25, depth=42, frequency=6.1, phase=0.35`, note `啊` duration 960 split at 480.

Backend pieces after split:
- first `啊`: ratio `0.5`, phase `0.35`
- second `-`: ratio `0.0`, phase `9.931857593448868`

Ctrl+J error: `split continuations have inconsistent vibrato phase and cannot be merged truthfully`; notes remained unmerged. Undo/redo/reload therefore had nothing to verify beyond unchanged two pieces.

Negative independent vibrato+normal lyric correctly rejected without mutation: `vibrato-bearing notes can only be merged when they are split continuations of one vibrato span`.

Artifacts: `05_vibrato_roundtrip_merged.png`, `06_vibrato_independent_negative.png`, `vibrato_merge_recheck.json`.
