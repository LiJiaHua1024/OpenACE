# Playback Error Clear Recheck

Date: 2026-11-28  
Bundle: `index-DfEGen12.js`  
Backend: restarted before test  
Implementation modified: no

## Result

The P3 stale-audio-error defect is fixed for the tested frozen-clock path.

## Quantitative evidence

- Normal playback baseline: advanced from `00:00.00` to `00:01.10` in `1.167s`; three sources scheduled; pause left transport at `00:01.14`.
- Frozen-clock simulation: transport stayed frozen at `00:01.14`; playback stopped with actionable error at `894ms`.
- Recovery: first playing sample at `170ms` already had **zero error banners**; no click was performed. Playback then advanced from `00:01.24` to `00:01.96` by `887ms` elapsed wall time.
- Scheduled source counts: baseline `0 → 3`; frozen attempt `3 → 6`; recovery `6 → 9`.
- Console errors/warnings: zero. Failed browser network responses: zero.

## Non-audio error logic check

Runtime reproduction of an unrelated non-audio error was not practical in the focused pass. Static source and built-bundle inspection confirm the clear is prefix-scoped rather than indiscriminate:

```ts
setError(current => current.startsWith('Audio output') ? '' : current)
```

The production bundle contains the equivalent minified logic `startsWith('Audio output') ? '' : current` semantics (with template-string quoting). Therefore non-`Audio output` errors are returned unchanged by this path.

## Screenshots/results

- `09_recheck_normal_playback.png`
- `10_recheck_frozen_error_visible.png`
- `11_recheck_recovery_banner_autocleared.png`
- `playback_error_clear_recheck_results.json`
- `non_audio_error_logic_check.json`
