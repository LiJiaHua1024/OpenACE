# Click-free live playback reconstruction QA

Visible Chrome 1272×837, real imported audio clip, rebuilt frontend/backend; repo unchanged.

Passed: five live volume edits during playback produced five paired outgoing/incoming `setValueCurveAtTime` events, each duration exactly 0.09s and 17-point equal-power curves (outgoing 1→~0, incoming ~0→1). Each old source stop was scheduled 0.12s in the audio-clock future, not immediate/currentTime. Transport positions advanced smoothly `00:00.71→00:01.30` across rapid edits. Exactly five delayed reconstruction stops occurred—no runaway unbounded buildup was evident. Pause produced a separate immediate/default `stop(0)`, and Stop reset transport to zero, so intentional hard-stop path remains. Console/network clean.

Not fully tested: manual clip fade/crossfade audible semantics, meter continuity, loop regression, and perceptual clicklessness/audio output. Evidence is instrumentation/transport-level, not acoustic proof.

Evidence: `playback_rebuild_results.json`, screenshots 01–03.

## Gap-focused continuation

Scripted fixture setup created two overlapping clips and manual 240-tick fade-in/out values, then browser playback was tested. Passed: playback scheduling produced many linearRamp automation events including complementary sine/cosine-like equal-power crossfade sequences reaching exact 0.0001/1 endpoints and mirror values around 0.5. Live edit again produced paired 90ms incoming/outgoing transition curves for both overlapping sources. Instrumented meter peak never collapsed to zero during rebuild: minimum observed approximately 0.0547, then recovered through 0.117→0.171→0.265→0.335, consistent with a brief equal-power dip rather than a decode/rebuild silence gap. Seek click moved transport to 00:01.75 and increased scheduled ramp count from 49 to 63, demonstrating rescheduling. Loop playback remains untested. Manual fade/crossfade evidence is scheduling/instrumentation-level, not perceptual proof.

## Loop regression final gap

Passed at instrumentation/transport level. A short arrangement loop was drawn over continuous audio and playback sampled for multiple cycles. Transport repeatedly climbed then restarted near zero: approximately `.28/.45/.60→.00`, `.16/.32/.47/.62→.03`, later `.58/.73→.13`, `.45/.60→.02`, and `.49/.64→.05`. Small nonzero first samples are sampling/RAF restart timing, not cumulative monotonic drift. A live volume-edit reconstruction during looping did not stop or break subsequent loop restarts. Pause after the samples worked. Perceptual clicklessness remains unproven.

Evidence: `06_loop_range.png`, `07_loop_live_edit.png`, JSON key `loop_regression`.
