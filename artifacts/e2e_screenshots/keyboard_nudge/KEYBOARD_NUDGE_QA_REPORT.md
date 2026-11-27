# Piano-roll keyboard nudge QA report

Date: 2025-11-27  
Surface: real visible Chrome, exact viewport `1272x837`  
Fixture: project `project_fd267883b19a`, track `track_675fdfececdf`, three Chinese lyric notes  
Build state: frontend rebuilt, backend restarted, browser cache-busted  
Implementation files: unchanged

## Verdict

All requested keyboard-nudging behavior passed. No implementation defect was confirmed.

The raw matrix initially reported two lower-clamp failures, but those were harness expectation errors: the script expected the final lower clamp one octave too early. A corrected supplement proved the true backend sequence is exact:

1. before lower clamping: pitches `34,36,31`
2. final collective clamp: pitches `27,29,24`
3. additional Shift+Down: unchanged `27,29,24`

Adjacent pitch intervals remained exactly `+2,-5` throughout.

A separate visibility concern was also checked: at default row height the low-clamped notes can be outside the visible piano range because vertical scrolling stops at a higher top pitch. However, zooming the Row height control down to `8` reveals all low-clamped notes clearly with selection intact. This is normal viewport/zoom behavior and is not counted as a keyboard-nudge defect. The first recording contains one overly conservative visibility annotation made before this correction; use the separate short visibility-correction recording/screenshot as the authoritative visibility evidence.

## Exact results

- Exact viewport and fixture: passed; initial notes `(240+240,p70)`, `(720+240,p72)`, `(1200+240,p67)`.
- Single selection: passed; UI displayed `1 selected`.
- Single ArrowRight: passed; selected note moved exactly one current grid step, `240 -> 360` ticks at 1/16 grid (`ppq/4=120`).
- Single undo: passed; exact `240` restored.
- Single redo: passed; exact `360` restored.
- Repeated ArrowLeft zero clamp: passed; note reached exactly tick `0` without becoming negative.
- Group ArrowLeft at zero: passed; no movement and no interval squashing.
- Group ArrowRight: passed; starts became `120,840,1320`; start gaps remained exactly `720,480` ticks.
- Group undo: passed; exact starts `0,720,1200` restored.
- Group redo: passed; exact starts `120,840,1320` restored.
- Text lyric input: passed; caret positions followed arrows `[2,1,2]` and all notes remained unchanged.
- Group semitone ArrowUp: passed; pitches `70,72,67 -> 71,73,68`.
- Group Shift+ArrowUp octave: passed; pitches `71,73,68 -> 83,85,80`.
- Upper collective clamp: passed; final pitches `94,96,91`, stable on further octave-up, preserving exact `+2,-5` intervals without squashing.
- Group Shift+ArrowDown octave: passed; upper state returned exactly `82,84,79`.
- Lower collective clamp: passed after corrected supplement; final pitches `27,29,24`, stable on further octave-down, preserving exact `+2,-5` intervals without squashing.
- Reload persistence: passed; exact backend state after reload remained starts `120,840,1320`, durations `240`, pitches `27,29,24`, lyrics `啊`.
- Toolbar overflow: passed; `.editor-toolbar` measured `scrollWidth=714`, `clientWidth=714`; body `1272/1272`.
- Console/network: passed; no unexpected console errors or failed network requests.

## Evidence files

- `keyboard_nudge_results.json` — raw matrix, including the two superseded harness false failures.
- `lower_clamp_supplement.json` — corrected lower-bound proof, passed.
- `low_visibility_probe.json` — Row height reached `8` for low-note visibility check.
- `00_initial_three_notes.png` — initial three-note fixture.
- `01_single_right_grid.png` — single-note grid nudge.
- `02_group_right_spacing.png` — group horizontal nudge.
- `03_text_input_arrows.png` — lyric input caret interaction.
- `04_group_upper_clamp.png` — upper clamp state/control evidence.
- `05_group_lower_clamp.png` — lower clamp state/control evidence.
- `07_group_lower_clamp_visible_scrolled.png` — default low visibility limitation evidence.
- `09_lower_clamp_visible_corrected.png` — all low notes visible at Row height `8`.
- `/home/ubuntu/screencasts/keyboard-nudge-qa/keyboard-nudge-qa-edited.mp4` — main interaction recording.
- `/home/ubuntu/screencasts/keyboard-nudge-low-visibility-check/keyboard-nudge-low-visibility-check-edited.mp4` — short visibility correction recording.
