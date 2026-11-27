# Loudness meter decay/reset retest

Visible Chrome 1272×837, corrected uncommitted build, fixture backend restarted; repo unchanged.

Passed:
- Controlled steady 440Hz clip initially measured stable `M/S/max -19.6`.
- Ten volume-down steps lowered momentary to `-25.6`; max remained prior `-19.6` as expected.
- Live rebuild continued measuring (`M -25.4`, S evolving `-22.5`).
- Pause decay no longer froze: M dropped immediately to about `-104/-108` while S decayed progressively `-25.2 → -28.1 → -30.5 → -36.8 → -112.7` over several seconds. M fell faster than S exactly as expected.
- Restarting before clip end recovered to `M -19.6` while S remained truthful `-22.9` during reintegration.
- Muted playback integrated true zero input: M about `-104.7` after 1.6s; unmute recovered `M -19.6`.
- Reset honesty was verified with a discriminating volume test: before reset `M -25.6 / S -22.4 / max -19.6`; 1s after reset `M/S/max -25.6`, proving old max/short-term state did not persist.
- Layout remained 215px-contained; console/network clean.

Caveat: an initial 5s-tone pass reached clip end before restart/reset, making those specific early readings invalid; the 20s-tone supplemental pass above is the valid evidence. Zero-gain sink inaudibility remains implementation-level rather than perceptual proof.

Evidence: `loudness_meter_retest_results.json`, screenshots `07_retest_volume_down.png` through `11_retest_valid_recovery.png`.
