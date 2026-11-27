# Truthful live loudness meter QA

Visible Chrome 1272×837, rebuilt/restarted; repo unchanged.

Passed: worklet loaded without console error; initial unavailable state `M/S/max −∞`; host AudioContext rate was 44100 and label correctly used honest `LUFS≈`; live playback produced finite changing values (`-21.6/-15.8`, short-term `-21.6/-17.0`) and persistent max; history canvas accumulated; panel fit sidebar at 215px wide; Reset honestly restored `M/S/max −∞` and cleared/shrank canvas history; pause/restart control still worked; console/network clean. Zero-gain sink implementation is present in code, but sandbox cannot prove no audible signal perceptually.

Defect/concern: silence decay is not truthful. Corrected mute test lowered readings only to `M/S -33.5` after 1s, and after pausing they remained exactly `M/S -33.5` 1.2s later rather than continuing toward silence/`−∞`. Earlier stop test similarly remained around `-18` instead of decaying. This suggests measurement freezes or stops receiving/processing silent tails when transport/mute rebuilds occur. Volume-down test was inconclusive because the program material/loop level varied and prior pan state had been altered; max short-term persisted correctly.

Evidence: `loudness_meter_results.json`, screenshots 00–06.
