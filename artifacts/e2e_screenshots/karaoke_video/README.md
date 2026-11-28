# Karaoke MP4 verification artifact

Fixture project: two contiguous Mandarin lyric notes (`你`, `好`), 0.5 seconds each at 120 BPM / 480 PPQ, with a 2-second master WAV.

Evidence files:
- `karaoke.mp4`: exported dynamic lyric video.
- `karaoke.ass`: generated ASS subtitle source; contains contiguous-phrase `{\kf50}` karaoke sweep timing, title, and OpenACE brand cards.
- `frame_060_early_second.png`: frame at 0.60s; first syllable is amber while the second is only beginning its sweep.
- `frame_075_halfway.png`: frame at 0.75s; first syllable is amber and the second is partially swept left-to-right.

Automated regression `test_mp4_lyric_video_is_timed_and_matches_audio_duration` now checks the ASS karaoke tags, exact media duration, and pixel-level amber/neutral distribution in the burned-in frame.
