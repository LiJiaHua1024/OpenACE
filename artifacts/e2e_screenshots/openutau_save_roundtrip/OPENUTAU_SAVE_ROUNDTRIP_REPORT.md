# OpenUtau host save-roundtrip validation

## Verdict

**Roundtrip passed with documented host-serialization caveats.** Official OpenUtau 0.1.576 loaded the OpenACE-generated validation USTX with the real temporary `友人` voicebank, rendered/played it after save, and wrote a host-serialized USTX via Ctrl+S. OpenACE's importer preserved all 8 note timings/pitches/lyrics, tempo, host singer, host phonemizer, and OpenACE `voice_id`. No lost singer/phonemizer, shifted notes, duplicated automation, or voice-id corruption was found.

## Host actions/evidence

- Before save: size `4005` bytes, sha256 `fae0b068615c3ca7326e98fc4e9708df92a33ee77ffd85c5cf12a530f9502afa`.
- Ctrl+S visibly reported `Project saved` in the OpenUtau status bar.
- After save: size `8478` bytes, sha256 `146f12be8aba919eb37dd9659b36da38559a389dde95c370d41f630e3f063201`.
- Log after save contains `Publish notification Save project`.
- Post-save playback from zero produced log entries `StartPlayback at 00:00:00`, `Part rendered`, `Waveform rendered and ready`, and `Publish notification Part rendered.`.
- GUI continued to show singer `友人`, `JA VCV & CVVC`, `WORLDLINE-R`; no missing singer/phonemizer error appeared.
- No voicebank or audio files were copied into this artifact directory.

## Exact OpenACE import result

- title: `OpenACE OpenUtau synthesis validation`
- ppq: `480`
- bpm: `100.0`
- tempo map: `[{'ticks': 0, 'bpm': 100.0, 'curve': 'step'}]`
- time signature: `4/4`
- track count: `1`
- track name/type: `Eugene validation` / vocal
- host singer: `友人`
- host phonemizer: `OpenUtau.Plugin.Builtin.JapanesePresampPhonemizer`
- OpenACE voice id: `zero-shot-reference`
- track volume/pan: `0.800018` / `0.0`
- track-level automation: dynamic `[]`, pitch cents `[]`
- clips: `0`
- note count: `8`

| # | start ticks | duration ticks | pitch | lyric | imported note pitch curve |
|---:|---:|---:|---:|---|---|
| 1 | 0 | 480 | 60 | `a` | — |
| 2 | 480 | 480 | 62 | `ka` | -40ms/-200¢, 40ms/0¢ |
| 3 | 960 | 480 | 64 | `sa` | -40ms/-200¢, 40ms/0¢ |
| 4 | 1440 | 480 | 65 | `ta` | -40ms/-100¢, 40ms/0¢ |
| 5 | 1920 | 480 | 67 | `na` | -40ms/-200¢, 40ms/0¢ |
| 6 | 2400 | 480 | 69 | `ha` | -40ms/-200¢, 40ms/0¢ |
| 7 | 2880 | 480 | 71 | `ma` | -40ms/-200¢, 40ms/0¢ |
| 8 | 3360 | 480 | 72 | `ya` | -40ms/-100¢, 40ms/0¢ |

## Before/after host serialization differences

OpenUtau rewrote the file substantially (543-line unified diff), but most differences are serializer/default expansion rather than musical corruption:

- added UTF-8 BOM and normalized YAML quoting/style;
- expanded `expressions` from empty to 27 standard OpenUtau expression descriptors;
- added legacy/top-level `bpm: 120`, `beat_per_bar: 4`, `beat_unit: 4` while preserving actual tempo map `100 BPM`—OpenACE importer correctly uses the tempo map and imports `100 BPM`;
- added track metadata `renderer_settings.renderer: WORLDLINE-R`, empty `track_expressions`, and `voice_color_names`;
- preserved exact track singer/phonemizer/mute/solo/volume/pan/color/name;
- extended voice-part duration `3840 → 4320` ticks. Since the last note still ends at `3840`, this is empty tail/part-bound padding, not shifted musical timing. OpenACE importer ignores part duration and re-export calculates `3840` again;
- because contiguous notes have `snap_first: true`, OpenUtau validation rewrote first pitch points to match the previous note interval: mostly `y=-20` after two-semitone rises and `y=-10` after one-semitone rises. This is documented OpenUtau behavior: snap-first automatically snaps the first pitch point to the previous note ending pitch.

## Caveats / potential importer concern

- The snap-first transition offsets are imported into OpenACE note-level `pitch_curve` as explicit pitch automation. This preserves the current rendered host behavior exactly, and re-exported USTX pitch data matches the host-saved pitch data exactly. However, it also means automatic host transitions may appear as user-authored pitch automation inside OpenACE; if notes are later reordered/edited, those frozen curves may not recalculate like OpenUtau snap-first semantics. This semantic risk was subsequently fixed in OpenACE: snap-first anchors are now treated as generated host transitions, stripped from user-authored pitch automation on import, and regenerated from the current neighboring note pitches on export. Re-importing this host-saved file now yields empty note pitch curves for all eight notes while preserving `pitch_snap_first`.
- Track-level automation remained empty; no duplicated default dynamic/pitch automation was created.
- Unrelated OpenUtau updater `403 rate limit` appears in logs and did not affect synthesis/save.

## Re-export consistency check

An additional in-memory OpenACE import→export check found:

- exact note timing/pitch/lyric sequence preserved;
- exact host singer/phonemizer preserved;
- note pitch data equal to host-saved pitch data;
- part duration returns to OpenACE's calculated `3840` ticks versus host-padded `4320`.

## Artifacts

- `before_openace_generated.ustx`
- `after_openutau_saved.ustx`
- `before_after.diff`
- `openace_import_result.json`
- `reexport_comparison.json`
- `reexported_from_host_saved.ustx`
- `openutau_log_before.txt`
- `openutau_log_after_save.txt`
- `00_before_save_gui.png`
- `01_project_saved.png`
- `02_singer_transport_zoom.png`
- `03_post_save_playback.png`
