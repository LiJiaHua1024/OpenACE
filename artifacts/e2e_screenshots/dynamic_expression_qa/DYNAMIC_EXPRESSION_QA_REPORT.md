# Dynamic expression QA report

Real visible Chrome QA through Playwright/CDP on branch `devin/1795696369-dynamic-expression`, using the explicit fixture server at `http://127.0.0.1:8787`. Viewport 1272×837. Fresh project: `project_f05abda7620e`; render job: `job_6b6fb5b50ca1`.

Important setup note: the original port-8787 server process had started before this branch’s Dynamic implementation and produced unprocessed audio. I restarted the fixture server from the current checkout before the valid run. The final results below are from the restarted current-branch server.

## Result: core audio effect PASS; job provenance FAIL

| Check | Result | Evidence |
|---|---:|---|
| Fresh two-note vocal | PASS | exact notes `(0,480,60)` and `(480,480,60)` |
| Dynamic neutral line | PASS | detected at y=79 vs expected 79.5 in a 153px lane; visually centered in usable lane |
| Rising Dynamic curve | PASS | exact endpoints `(0,0.0)` and `(960,1.0)` drawn through visible Line tool |
| Fixture render completion | PASS | job completed; WAV and diagnostic exist |
| Dynamic audio effect | PASS | first-note RMS `0.17056`, second-note RMS `0.34032`, ratio `2.00×`; peak `0.726`, no clipping |
| Diagnostic provenance | PASS visually | diagnostic explicitly says Dynamic lane gain post-processing, not neural conditioning |
| Job provenance | **FAIL** | final job API/message and visible job card only say `completed`; no Dynamic post-processing label remains |
| Playback | PASS | transport advanced `00:00.00 → 00:01.08`, pause state shown |
| Console/network health | PASS | zero console errors/network failures |

## Defect

The implementation writes `job.message = "rendered vocal with Dynamic post-processing"` during processing, but later overwrites it with `job.message = "completed"`. Consequently the completed job API and visible job card lose the provenance that the user was supposed to see. The diagnostic PNG does contain the correct provenance, but the job surface does not.

Visible job card evidence:

![Job card missing Dynamic provenance](https://app.devin.ai/attachments/33b44533-436b-47b2-baa7-a688c9bc7cae/06_render_job_card.png#w=1272&h=837)

Diagnostic provenance evidence:

![Diagnostic provenance](https://app.devin.ai/attachments/f3623fd8-c343-4c26-b3f4-50dedce28f62/evidence_diagnostic_provenance_crop.png#w=4200&h=180)

Minor polish observation: the diagnostic footer provenance collides slightly with the Matplotlib `frame` axis label, though the provenance remains readable.

## Visual/audio evidence

Dynamic lane neutral dashed line and exact rising line:

![Dynamic curve drawn](https://app.devin.ai/attachments/4788fbd3-e05a-4a8a-bfef-91086e72a633/05_dynamic_curve_drawn.png#w=1272&h=837)

Rendered waveform/RMS analysis:

![Dynamic audio analysis](https://app.devin.ai/attachments/14ac1069-aeb6-485a-a77d-38ecccee902a/evidence_dynamic_audio_analysis.png#w=1500&h=750)

Playback after render:

![Playback after dynamic render](https://app.devin.ai/attachments/5710cefa-d494-4a86-9c66-8747bdf571cb/07_playback_after_dynamic_render.png#w=1272&h=837)

## Artifact index

- Recording: `/home/ubuntu/screencasts/rec-3bf7833f-6956-4a4a-9aac-e2f946ea0cf2/rec-3bf7833f-6956-4a4a-9aac-e2f946ea0cf2-edited.mp4`
- Results JSON: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/dynamic_expression_qa/dynamic_expression_results.json`
- Rendered WAV: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/dynamic_expression_qa/dynamic_rendered_vocal.wav`
- Diagnostic image: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/dynamic_expression_qa/render_diagnostic.png`
- Empty console/network log: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/dynamic_expression_qa/browser_console.jsonl`

## Targeted provenance recheck

After the final-message fix, a concise current-branch recheck passed: render job `job_e123ebc2a527` completed with API message exactly `completed with Dynamic post-processing`, the visible job card showed the same text, diagnostic provenance remained correct, and there were no console/network errors. See `DYNAMIC_PROVENANCE_RECHECK_REPORT.md`.
