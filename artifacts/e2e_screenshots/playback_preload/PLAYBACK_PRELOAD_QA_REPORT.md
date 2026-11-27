# Playback preload optimization QA report

Date: 2026-11-27  
Surface: real visible Chrome, exact CSS viewport `1272x837`  
Mode: fixture backend, rebuilt/cache-busted frontend, restarted backend  
Implementation files: unchanged

## Verdict

The media preload/decode optimization itself works exactly: media is fetched once, decoded once in `OfflineAudioContext`, and the identical decoded buffer object is reused by playback. Warm start, seek restart, loop restart, normal-edit cache behavior, render-output preload, console, and network all passed.

However, one important startup defect remains and is reproducible: **the first playback after a fresh reload schedules the source almost immediately, but the newly created playback `AudioContext` clock remains effectively frozen for about 2.09 seconds**. Consequently the playhead/audio do not actually progress during that interval even though the context reports `running` and there is no autoplay warning. Warm restarts are fast and tightly synchronized.

This appears to be an unaddressed playback-context/audio-device initialization problem rather than a decode-cache miss. It matches the approximately 2.1 second startup latency observed before this optimization, so it is not evidence of a regression from the preload change, but the user-visible first-play latency remains.

## Exact measurements

### Initial preload after fresh reload

At 900ms after reload:

- media fetches: exactly `1`
- decodes: exactly `1`
- decode context: `OfflineAudioContext`
- media URL: `/renders/project_5383a7be8dc4/job_b4ed192a7b21/vocal.wav`
- fetch time: about `1.9ms`
- decode time: about `2.4ms`
- decoded duration: `2.4999773242630385s`
- decoded sample rate: `44100`

### First play after fresh reload

- click → `AudioBufferSourceNode.start()`: `4.7ms`
- click → nominal audible scheduling time: `4.7ms`
- click → first playhead text change: `23.4ms`
- source buffer identity: decode id `1`, decoded by `OfflineAudioContext`
- playback context state at source start: `running`

But the audio clock did not continue advancing:

- after `1.922s` wall time, playback context elapsed time was still only `0.01161s`
- position remained `00:00.01`
- reproducible controlled probe: context first meaningfully advanced at `2.0859s` wall time
- at `3.45s` wall time, position had reached only about `00:01.46`, consistent with a ~2s startup stall

Screenshots `08_fresh_first_play_at_1s.png` and `09_fresh_first_play_after_3s.png` show this clearly: at one second the transport is still `00:00.01` while the pause button is active.

### Warm stop/start

After the context had warmed:

- click → source start: `0.3ms`
- click → audible scheduling: `0.3ms`
- click → first playhead text change: `41.5ms`

After a render update:

- click → source start: `0.5ms`
- click → audible scheduling: `0.5ms`
- click → first playhead text change: `43.0ms`

Warm-clock stability over a 1.683s measurement window:

- wall elapsed: `1.6832s`
- audio-context elapsed: `1.68345s`
- ratio: `1.0001466`
- drift: sub-millisecond, well within tolerance

### Seek/restart while playing

A real click in the arrangement ruler sought to tick960:

- click → source restart: effectively `0ms` (`-0.2ms` is event-order/timer rounding)
- click → playhead update: `2.6ms`
- first updated position exactly `00:01.00|1.3.1`
- source offset exactly `1s`, duration remaining `1.499977s`

### Loop regression

- Loop control became active.
- Playback wrapped from `00:02.00|1.4.4` back to `00:00.01|1.1.1`.
- Two source starts occurred after loop playback began: initial start plus loop restart.
- Restart offsets compensated the rAF overrun (`0.008526s`, then `0.005442s`), avoiding an unmusical silence/gap.
- No transport regression was observed.

### Normal project edits and decode storms

A real piano-roll edit gesture produced multiple transient project updates. Before/after media counters were unchanged:

- media fetches: `1 → 1`
- decodes: `1 → 1`

So normal project edits did not cause duplicate media fetch or decode storms.

Harness note: the first edit coordinate was one pixel above the velocity lane and created a temporary stray note rather than editing velocity. This was still a valid multi-update project-edit storm probe. The stray note was deleted after testing; it is not an implementation defect.

### Render/output path update

After editing and rendering again through the visible `Render vocal` button:

- old URL: `/renders/project_5383a7be8dc4/job_b4ed192a7b21/vocal.wav`
- new URL: `/renders/project_5383a7be8dc4/job_966f87eb01ca/vocal.wav`
- output path changed: yes
- new media fetch count: exactly `1`
- total decode count increased `1 → 2`
- new decode context: `OfflineAudioContext`
- post-render playback used exact buffer identity decode id `2` in the playback `AudioContext`

### Console/network/autoplay

- console errors/warnings: none
- failed network responses: none
- autoplay/AudioContext warnings: none
- `AudioContext.resume()` calls observed: none, because the context reported `running`

## Artifact index

- `playback_preload_results.json` — full exact raw measurements
- `first_clock_stall_probe.json` — controlled fresh-reload clock-stall probe
- `playback_preload_run.log` — summarized raw run output
- `00_fresh_reload_preloaded.png`
- `01_first_play.png`
- `02_second_play.png`
- `03_seek_restart.png`
- `04_loop_regression.png`
- `05_normal_velocity_edit.png`
- `06_new_render_preloaded.png`
- `07_post_render_play.png`
- `08_fresh_first_play_at_1s.png` — key failure evidence
- `09_fresh_first_play_after_3s.png` — key failure evidence
- `/home/ubuntu/screencasts/playback-preload-qa/playback-preload-qa-edited.mp4` — interaction recording
