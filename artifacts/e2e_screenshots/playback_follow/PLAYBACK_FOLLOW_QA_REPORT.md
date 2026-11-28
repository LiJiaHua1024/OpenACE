# Playback Follow QA Report

Focused visible-Chrome test passed. Backend restarted/cache-busted; implementation untouched.

## Exact evidence

- Initial state: `playheadTicks=0`, `scrollTicks=0`, Follow on, loop disabled.
- During playback the first page occurred at `playheadTicks=3705`: `scrollTicks=2828.5428571428574`.
- Visible timeline width was `4191.428571` ticks; playhead was `876.457143` ticks inside the viewport after paging (~20.9%, consistent with paging near the requested 18% lead position).
- Stability samples after paging: playhead advanced `3705 → 3906 → 4196` while scroll stayed exactly `2828.5428571428574`; no jitter/page oscillation.
- Screenshot shows the same red playhead aligned across arrangement, tempo lane, and piano roll after paging.
- Follow off persisted as `localStorage=off`; during playback to `playheadTicks=3831`, `scrollTicks` remained exactly `0`.
- Re-enabling Follow while still playing immediately paged: at `playheadTicks=4633`, `scrollTicks=3310.5428571428574`.
- Reload after re-enable persisted `localStorage=on` and active Follow button state.
- Manual arrangement-ruler seek regression passed exactly at tick `960`.
- Loop regression passed: after creating loop `0–1920` and playing 2.6 s, playhead had wrapped to tick `520`.
- Console errors, page errors, and failed network responses: none.

Note: an intermediate piano-ruler probe using React-fiber state was ambiguous because fiber alternates can expose stale state; arrangement-ruler seek was objectively exact and prior piano-ruler grid snapping remains covered in grid-alignment evidence.

## Artifacts

- `playback_follow_results.json`
- `00_follow_paged.png`
- `01_follow_reenabled.png`
- `02_loop_regression.png`
- `03_manual_seek_arrangement.png`

Recording: `/home/ubuntu/screencasts/playback-follow-qa/playback-follow-qa-edited.mp4`
