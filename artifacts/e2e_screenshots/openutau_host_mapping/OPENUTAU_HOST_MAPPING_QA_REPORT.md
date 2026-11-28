# OpenUtau host singer mapping focused QA

## Verdict

**Passed.** The uncommitted host-interop UI exposes expandable `OpenUtau host` details on vocal tracks, persists singer/phonemizer mapping across reload, exports those exact values to USTX, and does not overwrite OpenACE voice/reference/render state.

## Evidence

- Vocal track shows expandable `OpenUtau host` details with separate singer/phonemizer inputs.
- Entered values:
  - singer: `友人`
  - phonemizer: `OpenUtau.Plugin.Builtin.JapanesePresampPhonemizer`
- Undo/redo behavior:
  - after one undo: singer remained `友人`, phonemizer became empty
  - after redo: both values returned
- After browser reload, both values remained populated.
- Backend project JSON retained mapping and preserved pre-existing OpenACE state exactly:
  - `voice_id`: `zero-shot-reference` before/after
  - `reference_voice_path`: `/home/ubuntu/repos/OpenACE/data/uploads/aspiration_reference.wav` before/after
  - `render_path`: `/home/ubuntu/repos/OpenACE/data/renders/project_1c093a015ab1/job_072330103560/vocal.wav` before/after
- Exported USTX first track contains:
  - `singer: 友人`
  - `phonemizer: OpenUtau.Plugin.Builtin.JapanesePresampPhonemizer`
  - voice-part comment still preserves `OpenACE voice_id: zero-shot-reference`
- Layout containment measurements passed:
  - details width `194px` within card width `219px`
  - both inputs within details
  - track list `clientWidth == scrollWidth == 235px`
- Console, page, and network errors: none in the valid run.

## Caveats / setup notes

- The first attempted legacy fixture was invalid for save testing because its pre-existing overlapping vocal notes made every project PUT fail with unrelated `422 vocal notes may not overlap`. A validated duplicate fixture without overlaps was then used. This was a fixture selection issue, not evidence of a host-mapping defect.
- The long phonemizer is visually truncated inside the narrow input, but the input remains inside the sidebar and the full value is preserved/exported. This is normal text-input scrolling behavior; no overflow defect was confirmed.

## Artifacts

- `00_project_loaded.png`
- `01_mapping_entered.png`
- `02_undo_state.png`
- `03_redo_state.png`
- `04_reload_persisted.png`
- `05_layout_final.png`
- `06_inputs_zoom.png`
- `exported.ustx`
- `openutau_host_mapping_results.json`
- `fixture.json`
