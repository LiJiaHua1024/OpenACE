# Note-split fix regression recheck

Environment: real visible Chrome over CDP at exact CSS viewport `1272×837`; frontend rebuilt, backend fully restarted in fixture mode, cache-busted page. Clean project `project_1278943df6f9`. No implementation files modified.

## Result: duplicate fix passed; one residual toolbar-layout defect remains

### Passed

- Context-menu split at exact tick960 produced exactly two backend notes after SSE settled:
  - `0+960`, lyric `啊`
  - `960+960`, lyric `-`
- Toolbar split chain produced exactly three unique notes: starts `0,480,960`; no duplicated IDs or continuations.
- Ctrl+E chain produced exactly four unique notes: starts `0,480,960,1440`; no duplicated IDs or continuations.
- Undo restored exact three-note state.
- Redo restored exact four-note state.
- Reload persisted exact four-note state.
- English `cat` terminal `/t/` split was rejected without mutation.
- Rejection overlay is readable inside `.piano-roll-wrap`:
  - text `Split must land inside a sustained vowel`
  - overlay box x `732.39`, y `292`, width `207.61`, height `27`
  - piano wrap x `236`, y `284`, width `714`, height `359`
- Console/network transport clean. The deliberate rejection produced the expected HTTP422 split response; the expected browser resource message was not counted as an app failure.

### Residual defect: toolbar still overflows and clips selection text

At exact `1272×837`, while the error overlay is visible:

```json
{
  "toolbar": [730, 714],
  "toolbarRight": 950,
  "selection": {"text":"1 selected","left":903.8984375,"right":965.8984375,"width":62}
}
```

Thus `scrollWidth != clientWidth`, and the selection label extends about `15.9px` beyond the visible piano toolbar edge. The screenshot shows clipped `1 selecte`. This means the overlay fix improved error readability but did not solve the pre-existing toolbar crowding/overflow requirement.

## Harness note

An intermediate continuation script incorrectly used empty-space clicks while the pencil tool was active, creating two disposable stray notes in the first recheck project. That harness artifact was discarded; final results above come from clean project `project_1278943df6f9` using the select tool.

## Evidence

- `note_split_fix_recheck.json`
- `notesplitfixclean.log`
- `20_fix_context_exactly_two.png`
- `21_fix_toolbar_chain_three.png`
- `22_fix_ctrl_e_chain_four.png`
- `23_fix_reload_exact_four.png`
- `24_fix_english_error_overlay.png`
