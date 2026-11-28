# Monophonic vocal-note overlap QA

Real visible Chrome, exact `1272x837`; frontend rebuilt/cache-busted (`index-DxQEsqhh.js`); backend restarted. No repo code modified.

## Verdict

Core overlap resolution passed with no backend overlaps, no console errors, and no save 422s. One coverage limitation: Quantize was exercised and remained clean, but the harness did not construct a meaningful quantize-specific collision, so that exact collision path remains untested.

## Exact evidence

- Exact legato boundary allowed: notes `0+240 你` and `240+240 好`; no overlap/rejection.
- New-note collision: created `240-600 啦` into note at `480`; resolution trimmed it exactly to `240+240`.
- Move collision: dragging following note left to `360` trimmed preceding `啦` exactly from `240+240` to `240+120`.
- Resize collision supplement: resizing first note into next note resolved back to exact non-overlap `120+120` before `240+240`.
- Nudge collision: selected first legato note `0+240`, ArrowRight moved it into second note; resolution produced exact `120+120` before `240+240`.
- Ctrl+Z restored exact pre-nudge `0+240`; Ctrl+Y reapplied exact resolved `120+120`.
- Paste overlapping clipboard: exact duplicate paste was resolved without overlap; only one pasted survivor remained, selection text `1 selected`, count `2→3`; no non-surviving pasted note was selected.
- Lyrics/phonemes survived trimming (`你 n i`, `好 x au`, `啦 l a` where applicable).
- Reload persisted final state exactly with no overlaps.
- Console/network clean; zero 422 save responses.

## Files

`note_overlap_results.json`; screenshots `01`-`12`, especially `10_exact_legato.png`, `11_nudge_collision.png`, `12_resize_collision.png`, `06_paste_resolved.png`, `09_reload.png`.
