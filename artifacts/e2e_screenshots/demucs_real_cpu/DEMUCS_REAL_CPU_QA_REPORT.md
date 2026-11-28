# Real production Demucs CPU QA

Visible Chrome 1272×837; backend started with `OPENACE_CI_SYNTH_FIXTURE=0`; repo unchanged.

Passed: UI upload of `mixed_source.wav`; `Separate vocal/instrumental` completed in 6.38s; job status completed, engine `Demucs`, `fixture:false`, not CI fixture. Separated vocal/instrumental tracks appeared live without reload, each with one clip. Both WAVs real stereo 44.1kHz/88200 frames/nonzero: vocal RMS 0.000726 peak 0.00262; instrumental RMS 0.21063 peak 0.41949; not identical, correlation 0.3617. Diagnostic provenance visibly says `Demucs htdemucs local stem separation`. Transport playback advanced `00:00.00→00:01.14`; mute on separated vocal persisted true. Reload retained 3 tracks/2 clips. Console/network clean.

Honest quality note: this validates production CPU orchestration/runtime and nonzero distinct stems only. The source is synthetic/pure-tone-like, so vocal stem very low level may reflect expected source/model behavior; no GPU or perceptual separation-quality claim is made.

Evidence: `demucs_real_cpu_results.json`, screenshots 01–06, diagnostic at backend output path.
