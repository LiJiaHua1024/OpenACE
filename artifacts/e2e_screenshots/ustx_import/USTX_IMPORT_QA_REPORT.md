# USTX import QA report

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, fixture backend, rebuilt frontend.

## Result

All requested USTX import checks passed. The fixture included both voice notes and a wave clip, so this was not voice-only coverage.

## Fixture

Created `ustx_import_roundtrip.ustx` through OpenACE's USTX exporter using:

- project tempo `100 BPM`
- time signature `3/4`
- vocal track `中文人声`, exact OpenUtau Purple source color `#BA68C8`, volume `0.5`, pan `0.25`
- Chinese notes/lyrics:
  - tick 0, duration 480, pitch 60, lyric `你`
  - tick 480, duration 480, pitch 62, lyric `好`
- user pitch curve on note 1: `12.5ms / +30 cents`
- vibrato on note 1: start ratio `0.25`, depth `40 cents`, frequency `4Hz`, phase quarter-cycle
- phoneme override on note 1: `n i`
- dyn automation: `(0,0.5)`, `(480,1.0)`
- pitd automation: `(0,-25)`, `(480,+50)`
- wave clip `Hook` backed by `/tmp/ustx_import_roundtrip.wav`:
  - position/start `480`
  - skip/source offset `240`
  - imported duration `320`
  - fade-in `48`, fade-out `96`

## UI behavior

- The visible `Import USTX` control was present in TransportBar.
- The real file chooser path was used (`method=file_chooser`, not direct input injection).
- `/api/import/ustx` returned HTTP 200.
- The imported project opened in the workstation.
- The project title became `ustx_import_roundtrip` because the endpoint intentionally uses the uploaded filename stem as project title.
- The piano roll visibly rendered the imported notes and Chinese lyric text; the second lyric `好` is clearly visible in the screenshot.
- The arrangement strip remained healthy and visibly showed the imported note span plus the `Hook` wave clip.
- The Dynamic lane visibly showed imported automation points.
- No console errors or network failures occurred.

## Backend contract verification

Verified in the HTTP response/project JSON:

- transport: BPM `100`, time signature `3/4`
- track type `vocal`, color `#BA68C8`, volume approximately `0.5`, pan `0.25`
- exact note tuples: `(0,480,60,'你')`, `(480,480,62,'好')`
- note 1 user pitch curve restored as `12.5ms/+30 cents`
- note 2 required serializer default pitch points were correctly ignored, leaving an empty user pitch curve
- vibrato restored: start ratio `0.25`, frequency `4Hz`, depth `40 cents`
- phoneme override symbol `n i` restored
- dynamic automation restored exactly at ticks `0/480`
- pitch-cents automation restored exactly at ticks `0/480` with `-25/+50`
- wave clip restored exactly:
  - `start_ticks=480`
  - `offset_ticks=240`
  - `duration_ticks=320`
  - `fade_in_ticks=48`
  - `fade_out_ticks=96`
  - `label=Hook`
  - resolved absolute source `/tmp/ustx_import_roundtrip.wav`

## Evidence

- `01_before_import.png`
- `02_after_import.png`
- `ustx_import_roundtrip.ustx`
- `ustx_import_results.json`
