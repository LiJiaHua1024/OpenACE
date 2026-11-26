# Piano-roll depth iteration QA report

Tested branch/worktree `devin/1795691203-piano-roll-depth` in a visible real Chrome window driven through Playwright/CDP against the production fixture server at `http://127.0.0.1:8787`. Primary viewport was exactly **1400×900 CSS pixels** (`devicePixelRatio=1`); a final responsive glance used exactly **1272×837**.

## Verdict

Most new piano-roll depth features are visibly operational. One significant editing defect remains: **multi-note drag cannot move notes earlier in time**. Pitch changes apply, but horizontal negative time movement is dropped. The likely implementation cause is that the shared `snap()` helper clamps negative deltas with `Math.max(0, ...)`.

## Results

| Check | Result | Evidence |
|---|---:|---|
| Exact 1400×900 viewport | PASS | `innerWidth=1400`, `innerHeight=900`, DPR 1 |
| Toolbar fit at 1400×900 | PASS | toolbar scrollWidth/clientWidth `842/842`; no visible overflowing children |
| Arrangement default has no repaint overlay | PASS | zero yellow overlay pixels before Alt-drag |
| Draw notes | PASS | three persisted notes `(360,360,60)`, `(960,360,62)`, `(1440,360,64)` |
| Select-tool marquee visibility/selection | PASS | dashed marquee visible while held; UI showed `2 selected` |
| Ctrl+C/Ctrl+V paste at playhead | PASS | count `3→5`; pasted starts `[2520,3120]` |
| Undo/redo around paste | PASS | count `5→3` on Ctrl+Z, then `3→5` on Ctrl+Y |
| Ctrl+D duplicate | PASS | persisted count `5→7` |
| Multi-select move later, relative spacing | PASS | `[2520,60] [3120,62] → [3000,61] [3600,63]`; spacing remained `(600 ticks, 2 semitones)` |
| Multi-select move back earlier | **FAIL** | inverse drag produced `[3000,60] [3600,62]`: pitch returned down 1, but start times did not move back by 480 ticks |
| VEL lane bars render | PASS | bottom lane visibly rendered bars; canvas pixel check found 10,575 bar-colored pixels |
| Drag velocity bar persistently | PASS | first note velocity persisted `90→3` |
| Right-click context menu | PASS | menu visibly showed Copy / Paste at playhead / Duplicate / Quantize / Delete |
| Context Copy/Paste | PASS | persisted count `7→8`, pasted at tick 2400 |
| Context Duplicate | PASS | persisted count `8→9`, duplicate start 2760 |
| Context Quantize | PASS | deliberately off-grid note `2797→2760` |
| Context Delete + undo/redo | PASS | count `9→8`, undo `8→9`, redo `9→8` |
| Alt-drag yellow repaint range | PASS | yellow region visible while held/after release; numeric range `0.47→1.63` |
| Toolbar fit at 1272×837 glance | PASS | toolbar scrollWidth/clientWidth `714/714`; no visible overflowing children |
| Browser console/network health | PASS | zero console errors and zero network failures captured |

## Main defect details

During the inverse drag test, the two selected notes were first moved later/up correctly:

- before: `[start=2520,pitch=60]`, `[start=3120,pitch=62]`
- after later/up drag: `[start=3000,pitch=61]`, `[start=3600,pitch=63]`

Dragging them back by the inverse vector should have restored `[2520,60]` and `[3120,62]`. Instead the persisted result was:

- `[start=3000,pitch=60]`
- `[start=3600,pitch=62]`

Thus vertical movement works bidirectionally, but horizontal movement earlier in time is ignored. This is a core piano-roll editing blocker because users routinely need to move phrases earlier as well as later.

## Key evidence

![Toolbar at exact 1400×900](https://app.devin.ai/attachments/3572c721-fe10-49c8-bd7f-69788e2aae42/01_1400x900_new_project_toolbar.png#w=1400&h=900)

![Visible dashed marquee selecting two notes](https://app.devin.ai/attachments/cb3d2dc3-87fb-4818-b558-f35881eb91b6/04_marquee_select_held.png#w=1400&h=900)

![Backward-drag defect state](https://app.devin.ai/attachments/7775fca7-03e5-4065-9514-f2837467f1fd/08_multiselect_move_back_earlier.png#w=1400&h=900)

![Velocity lane after persistent drag](https://app.devin.ai/attachments/420df96d-772c-4765-b745-b92ee77dfa0b/10_velocity_lane_after_drag.png#w=1400&h=900)

![Context menu](https://app.devin.ai/attachments/50277d81-576c-4d64-ac48-058c6e8a0d7c/11_context_menu.png#w=1400&h=900)

![Visible yellow Alt-drag repaint region](https://app.devin.ai/attachments/b4d1fb63-d534-4ab0-a9aa-17c0ba85d7a4/14_alt_drag_yellow_repaint_held.png#w=1400&h=900)

![1272×837 responsive glance](https://app.devin.ai/attachments/43120ac9-2286-4361-a73a-b8da90553a42/16_1272x837_glance.png#w=1272&h=837)

## Artifacts

- Recording: `/home/ubuntu/screencasts/rec-5b43cd6c-249d-4219-9aa6-ce89260b1238/rec-5b43cd6c-249d-4219-9aa6-ce89260b1238-edited.mp4`
- Results JSON: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/piano_depth_qa/piano_depth_results.json`
- Empty browser console/network log: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/piano_depth_qa/browser_console.jsonl`
- Screenshot directory: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/piano_depth_qa/`
