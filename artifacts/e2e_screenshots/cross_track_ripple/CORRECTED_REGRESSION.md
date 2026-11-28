# Corrected cross-track ripple regression

Real Chrome exact 1272x837; implementation unchanged. Valid evidence in `retry_results.json` and screenshots `30-34`.

All focused assertions passed:

1. Bottom-row context menu containment: rect `608,93` to `812,249`, arrangement viewport `236,58` to `950,258`, `inside=true` (`30_menu_bottom_retry.png`).
2. Single ripple then undo/redo:
   - selected `a_sel1` removed
   - downstream clips/notes/breaths/automation shifted exact 480
   - Ctrl+Z canonical exactly: true
   - Ctrl+Y single state exactly: true
3. Valid visible Ctrl multi-select before right-click (`32_multiselect_white_retry.png`) covering:
   - `a_sel1` 960-1440
   - overlapping `b_sel_overlap` 1200-1680
   - contiguous `c_sel_contig` 1440-1920
   Merged union was exactly 960-1920 = 960 ripple, not double-counted:
   - all three selected clips removed
   - `a_after` 2400→1440
   - `b_after` 2880→1920
   - unselected inside `u_inside` stayed 1200
   - notes/breaths/automation inside interval stayed at 1200/1440
   - downstream 2400 shifted exactly to 1440
4. Multi undo exact canonical: true; Ctrl+Y redo exact multi: true; reload exact multi persisted: true.
5. Console/network clean.

No defects found in this corrected focused regression.
