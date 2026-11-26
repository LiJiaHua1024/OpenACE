# Known Issues / Escape-Hatch Register

## Critical validation gaps

- Real GPU inference has not been run in this CPU-only cloud sandbox. `scripts/verify_local_gpu.py` is the required acceptance gate on a 12GB NVIDIA machine.
- Real SoulX-Singer/ACE-Step output quality, exact preprocess artifacts, and ACE-Step repaint/complete semantics still need physical GPU logs and listening validation.

## Current product gaps after the independent browser QA fix round

- Pitch automation affects SoulX target F0 and Dynamic automation is applied as explicitly labeled post-render gain; air/falsetto/tension/energy lanes still persist without affecting sound.
- Piano roll now has marquee/multi-select/copy-paste/duplicate/quantize/context menu/velocity lane and per-note vibrato editing, but still lacks per-note pitch handles, cross-track clipboard, and large-project performance proof.
- Arrangement now uses decoded waveform peaks and supports independent audio-clip/grouped-note dragging, edge trim, and split-at-cursor, but still lacks clip fades/crossfades and richer context operations.
- Repaint region selection is implemented via Alt-drag plus numeric seconds; the underlying ACE-Step repaint output has not been validated on GPU.
- MP4 export now burns timed ASS subtitles and matches audio duration, but it is not polished karaoke highlighting. On Linux hosts without CJK fonts, Chinese glyphs may render as tofu even though project/export text is valid UTF-8.
- `.ustx`/`.svp`/`.vpr` writers are structural implementations and must be opened in the real target applications for schema validation.
- Cantonese and Japanese phoneme coverage are incomplete; unsupported input correctly errors instead of silently becoming “la”.
- Render jobs now persist across backend restart, but interrupted jobs are marked failed rather than automatically requeued.
- Faster-whisper lyric transcription exists as a helper but is not yet integrated into the visible SVC/import workflow.
