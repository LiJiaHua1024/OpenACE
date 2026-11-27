# SVP contract QA report

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, backend restarted with `OPENACE_CI_SYNTH_FIXTURE=1`, frontend rebuilt.

## Result

All requested SVP export checks passed.

## Verified UI behavior

- Created project `SVP Contract QA` / `project_88002ac438cc` with notes, vibrato, pitch/dynamic/tension/air automation.
- Clicked the visible `SVP` export control.
- Browser download started successfully.
- Backend export endpoint returned HTTP 200 with a 4,267-byte `.svp` JSON file.
- UI remained healthy after export; title and piano roll remained intact.
- No console errors or network failures occurred.

## Verified file contract

- `version: 153`.
- `mainGroup.uuid` exactly matches `mainRef.groupID`.
- `mainRef.blickOffset: 0` and `blickAbsoluteBegin: 0`.
- `database` is `{"name":"zero-shot-reference"}`.
- `voice.voicing: 1.0` with zeroed vocal mode scalar fields.
- Vibrato attributes:
  - `tF0VbrStart: 0.125` seconds
  - `dF0Vbr: 0.4`
  - `fF0Vbr: 4.0`
- Flattened automation curves:
  - `pitchDelta.points = [0,-0.5,705600000,0.25]`
  - `loudness.points = [0,0,705600000,6]`
  - `tension.points = [0,0,705600000,1]`
  - `breathiness.points = [0,-1,705600000,0]`

## Evidence

- `01_workstation_before_svp_click.png`
- `02_workstation_after_svp_click.png`
- `svp_contract_export.svp`
- `clicked_download.svp`
- `svp_contract_results.json`
