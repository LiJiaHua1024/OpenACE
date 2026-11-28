# Mixed language final recheck

Backend on 8787 killed/restarted from current tree; cache-busted production frontend. No implementation changes.

## Result: passed

Tested the correct piano-roll `Lyrics…` batch editor (the Ctrl+Enter surface), not the side-panel correction list.

- Valid `你 hello 世界 world` into exactly five notes assigns exactly `你/hello/世/界/world` with coherent mixed phonemes: `你 [n,i]`, `hello [h,ə,l,oʊ]`, `世 [ʂ,ʂɻ̩]`, `界 [tɕ,iɛ]`, `world [w,ɝ,l,d]`.
- Fixture render `job_c3f1a843d3c0` completed without error.
- Japanese mixed input shows explicit warning: `Japanese script is not supported in Mixed Mandarin/English mode; use Mandarin or English lyric units.` Apply is disabled with title `Japanese script is not supported in mixed mode`; Ctrl+Enter does not mutate lyrics.
- Count mismatch `你 hello 世界` shows exact-count warning, disables Apply with title `Lyric token count must exactly match target notes`; Ctrl+Enter does not mutate lyrics.
- Correct-surface console/network clean.

Harness note: an initial quick pass mistakenly tested the separate side-panel batch correction control, which is not the Ctrl+Enter batch editor. The final correct-surface results above supersede that pass.

Evidence: `mixed_final_correct_surface.json`, `final_correct_01_japanese_blocked.png`, `final_correct_02_mismatch_blocked.png`, `final_03_render.png`, recording `/home/ubuntu/screencasts/mixed-language-final-recheck/mixed-language-final-recheck-edited.mp4`.
