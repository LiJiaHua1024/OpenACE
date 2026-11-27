# Piano-roll loop visualization QA

Environment: real visible Chrome over CDP at exact CSS viewport `1272×837`, backend restarted in fixture mode, frontend rebuilt/cache-busted. Real arrangement ruler drags, transport controls, piano toolbar, mouse wheel scroll/zoom, note/marquee/ruler/velocity interactions, backend JSON, canvas instrumentation, reloads, and audio-source instrumentation were used. No implementation files modified.

## Result

No implementation defect confirmed. Raw matrix: **13/15**; the two failures were harness measurement/interaction false negatives resolved by focused supplements:

1. The first note-drag attempt targeted pitch64 while the piano vertical view placed that pitch inside the velocity-lane hit area. After Shift-scrolling the piano view so pitch64 was visible in the note area, the note selected and dragged exactly `480→600`.
2. The first playback sample started inside the loop and stopped before enough restart events were captured. A focused supplement starting exactly at loop tick480 captured repeated nonzero-loop restarts.

## Verified behavior

- Arrangement drag `480–960` persisted exactly `{start:480,end:960,enabled:true}`.
- Piano and arrangement bands aligned exactly tick-for-tick at x `176`, width `112px` at shared zoom/scroll.
- Enabled piano band style alpha `0.094`; disabled subdued alpha `0.04`; arrangement also subdued `0.14→0.063` while range remained.
- Horizontal scrolling shifted both bands identically to x `-48`; zooming shifted/scaled both identically to x `-50`, width `114px`.
- Notes remain selectable/editable over the band: supplement selected note and moved pitch64 exactly `480→600`.
- Marquee drag inside band created no notes and did not clear loop.
- Piano ruler click inside band still sought (`1.1.1→1.2.3`) without loop interference.
- Velocity editing remained functional (`95→127` on tested note) without loop loss.
- Nonzero loop playback supplement captured restarts at intervals `0.5108, 0.4992, 0.4992s`; offsets near `0.51s` are correct because loop starts 0.5s into rendered audio.
- Reload restored same enabled piano visualization exactly.
- New project had no loop metadata, no piano band, and inactive Loop button.
- Layout exact, console/network/HTTP clean.

## Files

See screenshots `00` through `09`, raw `piano_loop_visual_results.json`, and focused supplement JSON files in this directory.
