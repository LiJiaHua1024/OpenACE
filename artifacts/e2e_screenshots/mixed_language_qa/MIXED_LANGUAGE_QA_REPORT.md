# Mixed Mandarin/English QA

Visible-Chrome fixture QA. Implementation unchanged.

## Defects

**P1 — mixed batch lyric distribution drops/non-assigns English units.** With five notes and input `你 hello 世界 world`, UI showed no count error, implying mixed tokenization counted five units, but backend notes became `你/好/世/界/啊` rather than preserving English words. English `hello`/`world` were not assigned; phonemes became Mandarin-style tokens such as `n ɛː i`, `h ɔː u`, etc. Render completed, but it was not rendering the intended mixed lyrics.

**P1 — unsupported Japanese in mixed mode is silently accepted/no-op rather than actionable.** Input `你 hello 世界 こんにちは` produced no visible validation error. Prior valid mixed state remained/changed only through the same lossy distribution behavior; no actionable Japanese rejection surfaced.

## Other results

- Mixed language option selectable; no crash. Phoneme editor mode opened without crashing.
- Fixture render completed (`job_a150bfb72b35`), but because English assignment failed this does not prove valid mixed rendering.
- Playback advanced (`00:00.96`) and console/network clean.
- Pure Mandarin `你好世界` and Cantonese `你好世界` distributed cleanly across four notes.
- Pure English regression was inconclusive in first pass because test used 2 words for 4 notes; supplement input had 4 words for 5 notes and correctly produced count error. No evidence of a pure-English defect, but valid pure-English render was not completed due time.

Artifacts: screenshots `00`–`06`, `mixed_results.json`, `mixed_supplement.json`, recording `/home/ubuntu/screencasts/mixed-language-qa/mixed-language-qa-edited.mp4`.
