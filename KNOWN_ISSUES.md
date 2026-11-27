# Known Issues / Escape-Hatch Register

## Critical validation gaps

- Real GPU inference has not been run in this CPU-only cloud sandbox. `scripts/verify_local_gpu.py` is the required acceptance gate on a 12GB NVIDIA machine.
- Real SoulX-Singer/ACE-Step output quality, exact preprocess artifacts, and ACE-Step repaint/complete semantics still need physical GPU logs and listening validation.

## Current product gaps after the independent browser QA fix round

- Pitch automation affects SoulX target F0; Dynamic, Air, Energy, Tension, and Falsetto automation are applied as explicitly labeled post-render DSP. Breath events still persist without affecting sound.
- Piano roll now has marquee/multi-select/copy-paste/duplicate/quantize/context menu/velocity lane, per-note vibrato editing, and per-note pitch handles, cross-track clipboard is regression-verified, and dense 3000-note 60FPS playback/scroll proof exists at 1400×900@2x.
- Arrangement now uses decoded waveform peaks and supports independent audio-clip/grouped-note dragging, edge trim, split-at-cursor, linear fade endpoints, clip gain, and automatic equal-power crossfades, clip copy/paste/duplicate/delete, and track duplicate/reorder/color/delete context operations, but still lacks richer project/media management.
- Repaint region selection is implemented via Alt-drag plus numeric seconds; the underlying ACE-Step repaint output has not been validated on GPU.
- MP4 export now burns timed ASS subtitles and matches audio duration, but it is not polished karaoke highlighting. On Linux hosts without CJK fonts, Chinese glyphs may render as tofu even though project/export text is valid UTF-8.
- `.ustx` is now source-derived against OpenUtau 0.10 and browser-export verified, including arrangement clips as wave parts and bidirectional browser-verified import, but still needs a real OpenUtau GUI open/render validation on a host with .NET 10. Per-clip gain is not representable in UWavePart and is therefore not exported/faked. Browser single-file USTX upload cannot access sibling audio files beside the original project, so external relative wave media may remain unresolved unless media is packaged or paths are reachable; `.svp` is source-derived through OpenUtau’s importer contract and browser-export verified but still needs real Synthesizer V validation; `.vpr` remains a structural implementation and must be opened in actual VOCALOID.
- Cantonese and Japanese phoneme coverage are incomplete; unsupported input correctly errors instead of silently becoming “la”.
- Render jobs persist across backend restart and recoverable interrupted jobs are automatically requeued; very extreme sparse-transient masters can still fail loudness validation loudly instead of being silently exported below spec.
- Local faster-whisper word-timestamp lyrics are integrated into audio import and verified on a real vocal. ASR can still misrecognize sung words, monophonic pitch extraction can fragment or merge syllables, and notes that cannot be aligned remain blank for user correction; a dedicated lyric-correction workflow and SVC-side lyric display are still missing.
