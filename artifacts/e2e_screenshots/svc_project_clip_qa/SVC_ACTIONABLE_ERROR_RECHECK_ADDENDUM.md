# SVC actionable-error recheck addendum

Date: 2026-11-28
Build: `frontend/dist/assets/index-B5QKLVag.js`, cache-busted visible Chrome, fixture backend.

Focused delta verification only; implementation not modified.

## Result: passed

1. Reloaded existing controlled project `project_832a3769a65b` and clicked the controlled arrangement audio clip.
2. The click selected the audio track (`selectedTrack=1`) and set exact source context:
   - path `clip_d275beb12e77_svc_clip_control_source.wav`
   - hint `Vocal2BGM/SVC input: visible clip segment · aligned to clip start`
   - SVC title `Convert the exact visible arrangement clip segment`
3. Although the audio track had no reference (`Zero-shot reference slot`), the SVC button was **not disabled**.
4. Clicking SVC did not create a job and instead showed the exact actionable error:

```text
Select a vocal track with an uploaded reference voice before SVC conversion
```

5. Reselecting the reference-carrying vocal track preserved the same clip source context/hint and showed `svc_reference_voice`.
6. Clicking SVC then completed job `job_a357938deda0` with exact clip identity and segment:

```json
{
  "clip_id": "clip_e32e014fd922",
  "source_start_s": 0.5,
  "source_end_s": 2.5,
  "arrangement_start_ticks": 960,
  "status": "completed"
}
```

Console errors/warnings: 0. Failed browser network responses: 0.

Minor observation, not a blocking defect: the actionable error banner remains visible after merely reselecting the valid vocal track; it is cleared when the subsequent conversion run starts. This did not block conversion.

Evidence:

- `21_svc_actionable_error_audio_track.png`
- `22_vocal_reselected_clip_context_preserved.png`
- `23_svc_conversion_after_reselect_completed.png`
- `svc_actionable_error_recheck.json`
- recording `/home/ubuntu/screencasts/svc-actionable-error-recheck/svc-actionable-error-recheck-edited.mp4`
