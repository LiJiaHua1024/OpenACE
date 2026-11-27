# Tempo map QA report

Date: 2026-11-27
Branch: `devin/1795696369-dynamic-expression`
Mode: visible Chrome at 1272×837, fixture backend, rebuilt frontend.

## Result

All requested tempo-map checks passed.

Harness transparency: fixture generation initially failed because the test harness did not construct the MIDI file with UTF-8 charset for Chinese lyric meta events. This was a harness issue, not an application defect; corrected fixture generation succeeded.

## Fixture

Created `tempo_change_fixture.mid`:

- PPQ 480
- tempo `120 BPM` at tick 0
- tempo `60 BPM` at tick 960
- vocal track `Tempo Vocal`
- distinctive notes:
  - tick 0, duration 240, pitch 60, lyric `慢`
  - tick 1200, duration 240, pitch 64, lyric `拍`

The second note starts at tick 1200 because the fixture intentionally places it after the tempo-change boundary using MIDI delta-time encoding.

## Import/backend verification

Imported through the visible **Import MIDI** control using the real browser file chooser.

Passed:

- `/api/import/midi` returned HTTP 200
- imported project opened as `tempo_change_fixture`
- backend `bpm` is `120.0`
- backend `tempo_map` exactly:
  - `{ticks: 0, bpm: 120.0}`
  - `{ticks: 960, bpm: 60.0}`
- backend notes exactly match the fixture positions/durations/pitches/lyrics
- notes/lyrics visibly render in the piano roll

## Transport verification

Clicked the piano-roll ruler at tick 1440.

Expected piecewise timing:

- tick 0–960 at 120 BPM = 1.0s
- tick 960–1440 at 60 BPM = 1.0s
- total = 2.0s

Observed transport:

- position `1.4.1`
- time `00:02.00`

A constant-120 BPM interpretation would incorrectly show `00:01.50`, so this specifically proves piecewise conversion in the visible transport.

## Playback interaction smoke

Started playback at tick zero and sampled the live transport after about 1.75 seconds.

Observed:

- live position `1.3.3`
- live time `00:01.76`
- estimated tick `1200`

This is consistent with piecewise tempo: after the 960-tick boundary, progression is at 60 BPM and remains in beat 3. Under constant 120 BPM playback, the playhead would already have reached beat 4. Playback was then stopped; no playback-related errors occurred.

## Health

No console errors or network failures occurred during import, seeking, or playback interaction.

## Evidence

- `tempo_change_fixture.mid`
- `01_before_import.png`
- `02_after_import.png`
- `03_seek_1440_piecewise_time.png`
- `04_playback_across_tempo_boundary.png`
- `tempo_map_results.json`
