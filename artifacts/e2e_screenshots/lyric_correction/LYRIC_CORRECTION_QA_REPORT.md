# Lyric correction QA report

Date: 2026-11-27
Scope: focused Lyric correction panel acceptance in real visible Chrome at 1272×837, fixture backend.

## Verdict

All focused acceptance checks passed. No Lyric-correction implementation defect was confirmed.

## Quantitative/functional evidence

- Four blank setup notes were present; section appeared with summary `4 notes · 4 missing lyrics` initially.
- Count mismatch `春风笑` (3 tokens vs 4 notes) displayed exact error `Lyric token count 3 does not match note count 4; nothing was changed.` Backend lyrics remained all empty.
- Exact continuous CJK paste `春风笑靥` mapped one Unicode character per note.
- After apply: backend lyrics exactly `['春','风','笑','靥']`; summary `4 notes · 0 missing lyrics`; row input values matched exactly.
- Backend phoneme counts regenerated: `[2,2,2,1]`; visible feedback included `ʈʂʰ uən`, `f əŋ`, `ɕ iau`, `iɛ`.
- Reload persistence passed: same lyrics and nonzero phoneme counts after browser reload/project GET.
- Per-note edit changed first lyric to `猫`; visible feedback `m au`; backend phoneme count remained nonzero.
- Undo/redo passed for row edit (`猫` → `春` → `猫`).
- Batch undo/redo passed independently: second batch `星辰大海` applied, undo restored `['猫','风','笑','靥']`, redo restored `星辰大海`.
- Layout geometry showed four rows inside the right panel with no input overflow and no phoneme/input overlap; screenshot review found compact professional layout.
- No console errors. Only expected `/api/events` SSE aborts occurred during deliberate reload.

## Incidental implementation concern outside this panel

The CLI `json_payload` helper crashed when given a long inline JSON array because `Path(raw).exists()` raises `Errno 36 File name too long`. I worked around it by passing a JSON file path. This does not affect the Lyric correction panel, but it is a real CLI robustness defect if inline JSON is intended for larger payloads.

## Evidence

- `lyric_correction_results.json`
- `01_blank_notes_section.png`
- `02_count_mismatch_error.png`
- `03_batch_applied_phonemes.png`
- `04_reload_persistence.png`
- `05_row_edit_phonemes.png`
- `06_final_layout.png`
- `07_batch_undo_redo.png`
