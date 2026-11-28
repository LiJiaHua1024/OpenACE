# Serialized Render Job Queue Focused Browser/API QA

Date: 2026-05-15  
Surface: real visible Chrome through Playwright/CDP, exact CSS viewport `1272×837`  
Backend: restarted with `OPENACE_CI_SYNTH_FIXTURE=1` and `OPENACE_CI_FIXTURE_DELAY_SECONDS=0.8`  
Frontend: rebuilt/cache-busted; implementation unchanged.

## Result

All requested focused checks passed. The queue serialized rapid vocal renders strictly in FIFO order, and no polling sample ever showed two jobs running simultaneously.

## Exact ordering evidence

Server-sent `render_job` publication order for wave 1:

1. `job_425a9b79f6e3` / `rq_vocal_1`: queued at `1795782976.6967108`
2. `job_425a9b79f6e3` / `rq_vocal_1`: running at `1795782976.6980991`
3. `job_9372cbcfe32e` / `rq_vocal_2`: queued at `1795782976.9437213`
4. `job_425a9b79f6e3` / `rq_vocal_1`: completed at `1795782979.7780063`
5. `job_9372cbcfe32e` / `rq_vocal_2`: running at `1795782979.7785754`
6. `job_9372cbcfe32e` / `rq_vocal_2`: completed at `1795782981.4095228`

Server-sent `render_job` publication order for wave 2:

1. `job_5055cc92eda1` / `rq_vocal_1`: queued at `1795782981.858233`
2. `job_5055cc92eda1` / `rq_vocal_1`: running at `1795782981.8597276`
3. `job_5149abbda024` / `rq_vocal_2`: queued at `1795782982.109279`
4. `job_5055cc92eda1` / `rq_vocal_1`: completed at `1795782983.53961`
5. `job_5149abbda024` / `rq_vocal_2`: running at `1795782983.5402784`
6. `job_5149abbda024` / `rq_vocal_2`: completed at `1795782985.2225013`

In both waves, the second job was created while the first was running, remained queued, and transitioned to running only after the first job's completion event. The completion-to-next-running gaps were approximately `0.00057s` and `0.00067s`.

## Additional evidence

- At the first-wave screenshot moment, backend states were first job `running`, second job `queued`.
- At the second-wave screenshot moment, backend states were likewise first job `running`, second job `queued`.
- A supplemental visual probe captured the render panel itself showing the first job `running` and second job `queued` at 650ms.
- Continuous API polling maximum simultaneous running count: `1`; overlap samples: none.
- Both jobs in both waves reached `completed`.
- Normal playback started after render completion.
- Exact layout had no horizontal overflow in body, right render panel, transport, or job cards.
- Console messages `0`; HTTP errors `0`; unexpected network failures `0`.

Note: the first rapid screenshot was taken before the frontend had applied the first running SSE update, so both new cards appeared queued in that early frame. The supplemental `05_third_wave_ui_running_queued.png` is the valid visual panel evidence for running+queued coexistence; backend SSE/API evidence is authoritative for ordering.

## Files

- Recording: `/home/ubuntu/screencasts/render-queue-authoritative/render-queue-authoritative-edited.mp4`
- Machine results: `render_queue_results.json`
- Supplemental visual probe: `render_queue_visual_probe.json`
- Key screenshots:
  - `00_first_wave_while_second_queued.png`
  - `01_first_wave_completed.png`
  - `02_second_wave_while_second_queued.png`
  - `03_second_wave_completed.png`
  - `04_playback_after_render.png`
  - `05_third_wave_ui_running_queued.png`
  - `06_third_wave_ui_completed.png`
