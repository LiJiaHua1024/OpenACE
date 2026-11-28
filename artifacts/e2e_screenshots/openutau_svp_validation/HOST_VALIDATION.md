# OpenACE SVP validation in official OpenUtau Linux x64 v0.1.576

Date: 2025-11-27  
Host: `/home/ubuntu/tools/openutau/OpenUtau`, title bar `OpenUtau v0.1.576.0`  
Input: `/tmp/openace_svp_validation.svp`  
Input SHA-256 before/after validation: `1a157a4ee5c19c62cefc8ca49627eb3fcf477ccc116e1963cb529f4d6b5e027d`  
The input file was not modified. A byte-identical copy is preserved as `input_copy_reference.svp`.

## Verdict

OpenUtau v0.1.576 **can directly open this `.svp`**. Both launching OpenUtau with the file path and using visible **File > Open** loaded the project without an error dialog or crash. Notes, exact Chinese lyrics, pitches, timing, vibrato, loudness automation, and a pitch-deviation lane are imported.

There is one important OpenACE exporter defect: **`pitchDelta` is written in semitone-scaled units even though SVP pitch deviation is specified in cents**. The visible/host-roundtripped pitch automation is therefore effectively flat instead of the intended OpenACE pitch automation.

## Exact evidence

### Direct and supported open paths

- Direct command-line open: `./OpenUtau /tmp/openace_svp_validation.svp` opened the arrangement visibly.
- Visible **File > Open** dialog, with the `Project Files` filter selected, listed `openace_svp_validation.svp`; selecting it and pressing Open loaded the same arrangement.
- No import error, unsupported-format dialog, crash, or data-loss prompt appeared.
- Only irrelevant Linux accessibility warnings appeared on stderr (`AT-SPI ... org.a11y.Bus ...`); no OpenUtau import error was logged.

Screenshots:

- `01_direct_cli_open_initial.png`
- `05_file_open_dialog_svp_listed.png`
- `06_after_file_open_svp.png`
- `06c_tracks_after_open_crop.png`

### Project and track structure

Observed in the host arrangement and in a clean OpenUtau `.ustx` round-trip saved from the freshly imported project:

- OpenUtau tempo/meter: **120 BPM, 4/4** — exact.
- Tracks shown: empty default **Track1** plus imported **SVP Lead**.
- Imported voice part: `name: SVP Lead`, `track_no: 1`, `position: 0`, `duration: 960` OpenUtau ticks.
- `Track1` is an OpenUtau default empty track retained above the imported track; it is not present in the OpenACE SVP. This is a host importer behavior/cosmetic interoperability limitation, not evidence of extra OpenACE notes.
- Track singer shown as **`[Missing] zero-shot-reference`** and phonemizer as **Select Phonemizer**. OpenACE writes `database.name = "zero-shot-reference"`, which is not an installed Synthesizer V/OpenUtau voice database. Notes still import, but synthesis voice identity does not resolve in this host.

The top-level SVP keys are only `version`, `time`, `library`, `tracks`, and `renderConfig`. There is **no project-title field** in the representative file; OpenUtau therefore shows/round-trips the project name as `New Project` until saved. The asserted OpenACE project title `OpenACE SVP Host Validation` cannot be validated through this SVP because no title is encoded in the file. The filename itself is also unrelated (`openace_svp_validation.svp`).

### Notes, Chinese lyrics, pitches, and timing

OpenUtau piano-roll inspection and clean round-trip agree exactly:

| Input SVP | OpenUtau round-trip / properties | Result |
|---|---|---|
| note onset `0`, duration `705600000` blicks | position `0`, duration `480` ticks | exact |
| lyric `你` | Lyric field shows `你` | exact Chinese lyric |
| pitch `60` | Tone `C4` | exact |
| note onset `705600000`, duration `705600000` | position `480`, duration `480` ticks | exact adjacent second note |
| lyric `好` | Lyric field shows `好` | exact Chinese lyric |
| pitch `62` | Tone `D4` | exact |

The notes initially render as narrow grey blocks because no usable singer/phonemizer is selected, but selecting them proves the Chinese lyrics are present in OpenUtau note properties. They are not lost or transliterated.

Screenshots:

- `02_pianoroll_overview_curves.png`
- `02c_notes_and_automation_crop.png`
- `03_note1_ni_c4_vibrato.png`
- `03c_note1_properties_crop.png`
- `04_note2_hao_d4.png`
- `04c_note2_properties_crop.png`

### Vibrato

First note input:

- `dF0Vbr: 0.35`
- `fF0Vbr: 5.5`
- `tF0VbrStart: 0.1`
- note duration at 120 BPM: 0.5 s

OpenUtau observed/round-tripped first-note vibrato:

- enabled/on
- depth **35** cents (`0.35 semitone * 100`)
- period **181.81818 ms** (`1000 / 5.5 Hz`)
- length **80%** (`(0.5 - 0.1) / 0.5`)
- fade in/out defaults `10`

Second note has input depth `0.0`; OpenUtau shows vibrato off / length `0`. This behavior is correct.

### Dynamics / loudness automation

Input SVP loudness curve:

```text
0 blicks          -> -1.8 dB
1411200000 blicks -> +3.6 dB
```

OpenUtau round-trip `dyn` curve uses tenths of a dB and samples exactly as expected:

| tick | round-trip `dyn` | equivalent |
|---:|---:|---:|
| 0 | `-18` | `-1.8 dB` |
| 240 | `-4` | approximately `-0.4 dB` on the linear ramp |
| 480 | `9` | approximately `+0.9 dB` |
| 720 | `22` | approximately `+2.2 dB` |
| 960 | `36` | `+3.6 dB` |

The blue DYN curve is visibly present in the piano roll. Dynamics automation therefore imports with correct shape, timing, sign, and scale.

### Pitch automation and exporter defect

Input SVP pitch curve:

```text
0 blicks          -> 0.0
705600000 blicks  -> 0.8
1411200000 blicks -> 0.0
```

OpenUtau round-trip `pitd` curve is present from tick `0` through `960`, but its range is only **0 to 1 cent**. At tick 480 it is `1`, then it returns toward `0`.

This is not an OpenUtau failure. The official Synthesizer V scripting documentation defines `pitchDelta` / Pitch Deviation in **cents**, range `-1200..1200`. OpenACE currently does this in `openace/exporters/svp.py`:

```python
# pitchDelta is semitones; loudness is dB; tension/breathiness are -1..1.
"pitchDelta": _svp_curve(project, track.automation.pitch_cents, lambda value: value / 100.0),
```

Because `track.automation.pitch_cents` is already in cents, dividing by `100.0` writes semitone-scaled values into a cents field. If the OpenACE source automation was intended to reach `+80` cents, the SVP should contain `80`, not `0.8`. OpenUtau correctly reads the file literally as `+0.8` cents and rounds its sampled cent curve to at most `1` cent.

**Precise exporter fix needed:** remove the `/ 100.0` conversion for SVP `pitchDelta` and write OpenACE pitch-cents automation in cents directly. The nearby comment is also wrong: SVP `pitchDelta` is cents, not semitones.

### Empty / absent automation

The input has empty `tension` and `breathiness` point arrays. They are not expected to produce curves. No tension/breathiness automation defect can be claimed from this fixture.

A constant `voic` curve at `100` appears in the OpenUtau round-trip because the input voice object has `voicing: 1.0`; this is host normalization of the voice base parameter, not evidence of OpenACE writing a voicing automation lane.

### Mixer/color metadata not preserved by host

The input track has `gainDecibel: -1.938200260161128`, `pan: 0`, and color `7c5cff`. The clean OpenUtau round-trip shows volume `0`, pan `0`, and color `Blue`. Current OpenUtau SVP importer does not appear to preserve these SVP mixer/color fields. This is a host importer limitation, not an OpenACE exporter defect.

## Round-trip artifact

`openace_svp_clean_roundtrip.ustx` was saved from a fresh, unmodified OpenUtau import using the host UI. It contains exactly two notes (`你`/`好`) and is the machine-checkable source for the exact values above. `host_parse_summary.json` contains the parsed comparison.

During an initial exploratory pass, two tiny unintended `a` notes were created by clicking while the pencil tool was active; that contaminated exploratory save was discarded as evidence. The final clean round-trip was created after re-opening the original SVP and using the selection tool, and contains exactly the two source notes.

## Files

- `input_copy_reference.svp` — unchanged byte-identical input copy
- `openace_svp_clean_roundtrip.ustx` — clean host round-trip used for quantitative validation
- `host_parse_summary.json` — machine-readable extracted values
- `01_direct_cli_open_initial.png` — direct CLI open
- `02_pianoroll_overview_curves.png` — piano-roll notes/vibrato/automation overview
- `02c_notes_and_automation_crop.png` — cropped notes/curve detail
- `03_note1_ni_c4_vibrato.png` / `03c_note1_properties_crop.png` — first-note `你`, C4, vibrato properties
- `04_note2_hao_d4.png` / `04c_note2_properties_crop.png` — second-note `好`, D4 properties
- `05_file_open_dialog_svp_listed.png` — `.svp` visible in Project Files open dialog
- `06_after_file_open_svp.png` / `06c_tracks_after_open_crop.png` — arrangement after File > Open
- `07_clean_roundtrip_saved.png` — saved clean round-trip state

---

# Follow-up validation of fixed exporter output

Date: 2025-11-27  
Input: `/tmp/openace_svp_validation_fixed.svp`  
Input SHA-256: `20fc076b670acf0d8e52ccc0182240a2044a4f464925604cd202c685772baf61`  
The fixed input was not modified. A byte-identical copy is preserved as `input_fixed_reference.svp`.

## Fixed-input verdict

The two confirmed OpenACE exporter defects are **fixed for this fixture** in real OpenUtau v0.1.576:

1. `pitchDelta` now contains cents directly: input points are `0 → 80 → 0`, and the clean OpenUtau round-trip pitch-deviation curve reaches exactly **+80 cents**.
2. The database name is now empty. The host no longer displays `[Missing] zero-shot-reference`; it truthfully displays generic **`[Missing]`** with **Select Phonemizer**, because no real Synthesizer V voice database is available.

No remaining OpenACE exporter defect was found in this fixed fixture. Remaining limitations are host/format limitations rather than exporter regressions.

## Exact fixed-file observations

### Open and singer state

- Directly launching OpenUtau with `/tmp/openace_svp_validation_fixed.svp` opened the project without error or crash.
- Track `SVP Lead` appears with singer line **`[Missing]`**, not `[Missing] zero-shot-reference`.
- OpenUtau still retains its empty default `Track1` above the imported track.
- No voice is actually selected; the user must still select a real singer/phonemizer before synthesis. This is expected because an empty database name cannot identify a voice.

Screenshots:

- `08_fixed_direct_open_missing_empty_singer.png`
- `08c_fixed_track_singer_crop.png`

### Notes, lyrics, vibrato, and timing

The clean fixed round-trip `openace_svp_fixed_roundtrip.ustx` still contains exactly two notes:

| position | duration | tone | lyric | vibrato |
|---:|---:|---:|---|---|
| 0 | 480 | 60 / C4 | `你` | length80, period181.81818ms, depth35 cents |
| 480 | 480 | 62 / D4 | `好` | length0/off |

These values are unchanged and correct.

### Pitch-deviation automation — fixed

Fixed input curve:

```text
0 blicks          -> 0 cents
705600000 blicks  -> 80 cents
1411200000 blicks -> 0 cents
```

Clean OpenUtau round-trip `pitd` samples:

| tick | cents |
|---:|---:|
| 0 | 0 |
| 240 | 50 |
| 480 | 80 |
| 720 | 50 |
| 960 | 0 |

The peak is exactly the expected approximately +80 cents. The nonzero intermediate values reflect OpenUtau's curved interpolation of the SVP linear control points, but the exact endpoint/peak values are correct and the full curve range is `0..80` cents rather than the previous defective `0..1` cent.

Screenshots:

- `09_fixed_pianoroll_pitch80.png`
- `09c_fixed_notes_curves_crop.png`
- `11_fixed_pitd_lane_selected.png`
- `11c_fixed_pitd_curve_crop.png`

### Dynamics automation — unchanged and correct

Clean fixed round-trip `dyn` samples remain correct:

| tick | USTX dyn | equivalent |
|---:|---:|---:|
| 0 | -18 | -1.8 dB |
| 240 | -4 | about -0.4 dB |
| 480 | 9 | about +0.9 dB |
| 720 | 22 | about +2.2 dB |
| 960 | 36 | +3.6 dB |

### Remaining limitations in fixed validation

- Empty singer still displays as generic `[Missing]`; this is truthful host behavior for no database, not the previous incorrect `zero-shot-reference` leakage.
- OpenUtau still adds/retains empty default `Track1`.
- OpenUtau still does not preserve SVP mixer gain/pan or display color in its round-trip.
- The SVP fixture still has no project-title field, so project title interoperability remains unavailable by format/content rather than a new exporter failure.
- Tension/breathiness arrays remain empty in this fixture and therefore remain untested.

## Fixed-validation files

- `input_fixed_reference.svp` — unchanged byte-identical fixed input copy
- `openace_svp_fixed_roundtrip.ustx` — clean host round-trip for fixed input
- `host_parse_summary_fixed.json` — machine-readable fixed-input comparison
- `08_fixed_direct_open_missing_empty_singer.png` / `08c_fixed_track_singer_crop.png`
- `09_fixed_pianoroll_pitch80.png` / `09c_fixed_notes_curves_crop.png`
- `10_fixed_roundtrip_saved.png`
- `11_fixed_pitd_lane_selected.png` / `11c_fixed_pitd_curve_crop.png`
