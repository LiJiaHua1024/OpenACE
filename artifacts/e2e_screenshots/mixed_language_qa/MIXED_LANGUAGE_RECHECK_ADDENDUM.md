# Mixed language recheck addendum

Backend was killed and restarted from the current tree before browser testing; frontend production build cache-busted.

## Passed

- Exactly five notes + `你 hello 世界 world` now distributes exactly as `你/hello/世/界/world` when language selection is allowed to settle.
- Backend phonemes are coherent mixed phonemes: `你 [n,i]`, `hello [h,ə,l,oʊ]`, `世 [ʂ,ʂɻ̩]`, `界 [tɕ,iɛ]`, `world [w,ɝ,l,d]`.
- Valid mixed fixture render `job_cf02f967ff7e` completed with no error; playback advanced to `00:00.91`.
- Pure Mandarin five-character regression and pure English five-word regression both distributed with no inline error.
- Console/network in final valid render path clean.

## Remaining defect

**P2 — pure Japanese in mixed mode is still not actionably surfaced in the lyric UI.** Applying `你 hello 世界 こんにちは` leaves `.inline-error` empty and the Apply button enabled. The backend rejects the invalid project save (observed as a 422 in the first pass), but the user is not shown the explicit unsupported-script message in the lyric correction workflow.

## Timing caveat

Selecting Mixed then immediately applying within ~200ms can race the asynchronous language save and cause a 422/no-op. Waiting ~1.3s after language selection produced the correct result. This may merit a frontend save-ordering fix, but was not counted as a separate defect in this quick recheck.

Evidence: `recheck2_00_valid_mixed.png`, `recheck2_01_japanese.png`, `recheck2_02_render_playback.png`, `mixed_recheck_results.json`, `mixed_recheck2_results.json`, `mixed_recheck2_render.json`, recording `/home/ubuntu/screencasts/mixed-language-recheck/mixed-language-recheck-edited.mp4`.
