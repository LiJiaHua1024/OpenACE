# Sample-Accurate Lookahead Loop QA Report

Date: 2025-11-28
Build: uncommitted lookahead-loop implementation in `/home/ubuntu/repos/OpenACE`
Browser: visible Chrome driven through Playwright/CDP
Backend: fixture backend at `http://127.0.0.1:8787`, restarted/cache-busted before testing
Instrumentation: in-page WebAudio instrumentation of `OscillatorNode.start/stop/disconnect` and `AudioBufferSourceNode.start/stop/disconnect`. Historical `start()` calls were **not** counted as audible when the node was stopped/disconnected before its scheduled start.

## Verdict

The core sample-accurate lookahead loop implementation passes the primary seamless-loop requirements:

- 120 BPM one-bar loop clicks were exactly 500 ms apart across three measured boundaries; the prior 34.83 ms loop-boundary stretch is gone.
- Scheduled outgoing source stop times and replacement loop-start source times aligned to the measured boundary with **0.0 ms maximum deviation**.
- No audible duplicate clicks, interleaving, click storms, early replacement sources, late loop-start sources, or audible source overruns were detected in the baseline or snapped non-bar loop.
- Seek, loop disable, and loop-range change during the lookahead window invalidated their pending generations; no pending source resurrected audibly.
- Piecewise tempo looping followed exact 500 ms / 461.538 ms beat spacing.
- Follow paging and synchronized arrangement/tempo/piano playhead visuals remained correct.
- Console, page-error, and network-failure logs were clean in every formal phase.

One intermittent defect remains in the mute/edit rebuild edge case, detailed below.

## Defect

### P2 — intermittent metronome boundary-click dropout/phase shift when a mute rebuild races loop commit

A mute toggle was issued inside the lookahead window before a one-bar loop boundary.

First reproduction:

- last pre-rebuild audible click: `304.915147`
- expected loop-boundary downbeat: `305.415147`
- that downbeat was canceled before sounding during the rebuild/loop invalidation sequence
- the next audible click occurred at `305.961587`
- resulting audible interval: **1046.44 ms**
- subsequent rebuilt click grid remained offset by about **46.44 ms** from the original musical grid (`x.961587` rather than `x.915147`)

Second identical reproduction:

- all intervals exactly `500 ms`
- no missing click and no phase shift

Interpretation: this is an intermittent race between continuous playback rebuild and pending-loop commit/invalidation. It did not duplicate audio or clicks, but it can drop the boundary click and leave the metronome phase shifted until a later restart. This violates the “edit/mute rebuild near boundary … metronome stays clean” requirement in the failure case.

## Quantitative results

### 1. 120 BPM one-bar loop, multiple boundaries

Loop range: `0–1920` ticks at 120 BPM (2 seconds).

Metronome:

- audible clicks: 17
- intervals: all exactly `0.5 s`
- min/max interval: `500.0 ms / 500.0 ms`
- exact audible same-time duplicates: 0
- intervals under 350 ms: 0
- canceled future oscillator `start()` history: 12 nodes, all stopped/disconnected before sounding

Reached boundaries:

| boundary AudioContext time | crossing outgoing sources | max stop deviation | loop-start replacement sources | early/late/overlap |
|---:|---:|---:|---:|---|
| 185.66984126984127 | 7 | 0.0 ms | 2 | none |
| 187.66984126984127 | 7 | 0.0 ms | 2 | none |
| 189.66984126984127 | 7 | 0.0 ms | 2 | none |

### 2. Seek while lookahead restart was pending

The seek landed inside the lookahead scheduling window. The deferred graph had been initiated before the seek; some async graph nodes materialized just after the seek and were then invalidated.

- invalidated pending source nodes: 14
- uncancelled invalidated pending sources: 0
- post-seek audible metronome intervals: all exactly `500 ms`
- exact audible duplicates: 0
- intervals under 350 ms: 0

The one large raw interval (`845.986 ms`) is the expected phase transition across the user seek, not interleaving; the post-seek grid itself was exact.

### 3. Disable loop while pending

Loop was disabled inside the lookahead window.

- pending generation nodes observed: 14
- uncancelled future sources after disable: 0
- playback continued past the old boundary without jumping back to loop start
- post-disable position was `2.3.1 / 00:03.11`
- audible metronome intervals stayed exactly `500 ms`
- exact audible duplicates: 0

### 4. Change loop range while pending

The arrangement ruler drag was performed during the lookahead window and extended the loop to `0–2880` ticks.

- exact pre-change deferred generation nodes: 14
- canceled before start: 14
- uncancelled/resurrected pre-change pending sources: 0

Caveat: ruler dragging live-updates intermediate loop ranges, so the edit itself perturbs playback position/phase before the final range is reached. Therefore this test conclusively verifies pending-source invalidation/no resurrection, but it is not a clean isolation of whether an atomic final range edit should preserve playback phase.

### 5. Mute/rebuild near boundary

- run 1: intermittent failure described above (`1046.44 ms` gap; no duplicates)
- run 2: all intervals exactly `500 ms`
- playback continued in both runs
- exact audible duplicate clicks: 0 in both runs

### 6. Arbitrary snapped non-bar loop

Loop range: `0–1440` ticks (3 beats at 120 BPM).

- audible clicks: 14
- intervals: all exactly `500 ms`
- exact audible duplicates: 0
- intervals under 350 ms: 0
- downbeat pattern repeated every loop as expected for restart at tick zero

Reached boundary source validation:

| boundary AudioContext time | crossing outgoing sources | max stop deviation | loop-start replacement sources | early/late/overlap |
|---:|---:|---:|---:|---|
| 391.95514739229026 | 6 | 0.0 ms | 3 | none |
| 393.45514739229026 | 6 | 0.0 ms | 3 | none |
| 394.95514739229026 | 6 | 0.0 ms | 3 | none |

### 7. Piecewise tempo loop

Tempo map: base 120 BPM, step point at tick `960` to 130 BPM; loop `0–1920` ticks.

Observed audible intervals only contained the expected values:

- `500 ms` for 120 BPM beats
- `461.538 ms` for 130 BPM beats
- no duplicates, no intervals under 350 ms, no storm

The first audible click after playback start was beat 2, so the first measured transition sequence began `500 → 461.538 → 461.538`; subsequent loop cycles showed the expected `500 → 500 → 461.538 → 461.538` pattern.

### 8. Visual, Follow, and loop-band regression

- loop band visually covered the correct arrangement/piano region in the one-bar loop screenshot
- red playhead was phase-aligned across arrangement, tempo lane, and piano roll
- Follow regression paged after seeking near the right edge: `3.1.1 / 00:03.79` before playback, then `3.4.4 / 00:05.59` during playback with the playhead visible and aligned
- final project state restored to tempo map `[]`, time signature 4/4, loop `0–1920` enabled

### 9. Console/network

All formal phases had:

- console errors/warnings: 0
- page errors: 0
- failed network responses: 0

## Evidence index

- `10_lookahead_loop_timing_analysis.png` — combined quantitative interval chart
- `00_bar_loop_playhead_phase.png` — one-bar loop visual phase/loop band
- `01_seek_while_pending.png` — seek-during-pending test
- `02_disable_loop_while_pending.png` — loop-disable test
- `03_mute_rebuild_near_boundary.png` — mute/rebuild test
- `04_nonbar_loop.png` — non-bar loop test
- `05_piecewise_loop.png` — piecewise tempo loop test
- `06_follow_regression.png` — Follow paging regression
- `07_final_clean_project.png` — final cleaned project state
- `08_change_loop_while_pending.png` — loop-range-change test

Raw JSON snapshots/results are beside this report in the same directory.
