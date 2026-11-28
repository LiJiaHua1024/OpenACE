# Separation project-clip awareness QA

Visible-Chrome fixture QA on project `project_832a3769a65b`; backend restarted after implementation because backend does not hot-reload. Implementation unchanged.

## Result: passed; no product defects found

- Controlled clip context showed `Vocal2BGM/SVC/separation input: visible clip segment · aligned to clip start`; Vocal2BGM/SVC titles remained correct.
- Controlled job `job_5b29d1759b3f`: `clip_id=clip_e32e014fd922`, source `0.5–2.5s`, captured arrangement start `960`.
- While queued behind a vocal render, source clip was dragged `960→1440`; both stems integrated at `start_ticks=1440`, `duration_ticks=1920`.
- Excerpt exactly 2s and bit-identical to controlled source `[0.5:2.5]` (`maxerr=0.0`). Both stems exactly 2s/48000 samples.
- Duplicate same-path omission returned actionable HTTP 422: `multiple arrangement clips use this source audio; pass clip_id explicitly`.
- Explicit duplicate click job `job_61037efd71ee`: `clip_id=clip_dup_svc_probe`, source `1.0–1.5s`; excerpt exact; both stems 0.5s and integrated at tick 48/duration 480.
- Arbitrary upload job `job_7191f8c4237b`: `clip_id=null`, both stems exactly 1.5s and integrated at zero/duration 1440.
- Reload persisted all generated stem clips. Playback scheduled controlled source with offset .5 at ≈1.5s, duplicate segment at ≈0.1s, and stems at their arrangement positions; console/network clean.

Setup note: the first run accidentally used the stale pre-restart backend and produced unscoped zero-start/full-length stems. After restarting the backend, all focused assertions passed as above; stale-run outputs were not counted as product defects.

Evidence: `separation_results.json`, screenshots `00`–`05`, recording `/home/ubuntu/screencasts/separation-project-clip-qa/separation-project-clip-qa-edited.mp4`.
