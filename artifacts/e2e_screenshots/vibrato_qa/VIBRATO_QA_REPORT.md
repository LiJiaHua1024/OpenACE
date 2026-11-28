# Per-note vibrato editor — real Chrome QA

## Scope and method

Visible Chrome 1272x837 was driven with Playwright over CDP against the fixture server. QA covered a fresh project, note creation/selection, context-menu and toolbar editor entry, enabled/disabled control state, slider edits, backend persistence, canvas indication, one-step undo/redo, popover layout, and console/network health.

## Outcome

Core vibrato editing functionality passed, but one visual layout defect remains.

## Defect

### Context-menu popover spills into the automation lane for low notes

Right-clicking the low C4 note opens the editor at the click position. The popover extends to y=812 while the piano-roll/editor wrap ends at y=643, so it overlaps the automation area by about **169 px**. It remains inside the viewport and all controls are usable, but it obscures unrelated automation controls instead of being repositioned/clamped within the piano-roll surface.

Evidence: `03_vibrato_editor_context_low_note.png`

## Results

| Check | Result | Evidence |
|---|---|---|
| Fresh project and note creation | PASS | One exact note `[start=0,duration=960,pitch=60]`; project `project_54aed0a27055` |
| Toolbar disabled-state logic | PASS | Disabled before selection; enabled for exactly one selected note |
| Context menu entry | PASS | `Vibrato…` visible/enabled; editor opens |
| Disabled controls before Enable | PASS | All four sliders disabled before Enable |
| Controls after Enable | PASS | All four sliders enabled |
| Slider editing | PASS | UI values `start=0.60`, `depth=80`, `rate=6.2`, `phase=1.43` |
| Visual labels | PASS | Labels match controls: `Start 60%`, `Depth 80¢`, `Rate 6.2Hz`, `Phase 1.43` |
| Backend persistence | PASS | Exact match after close: `start_ratio=0.6`, `depth_cents=80.0`, `frequency_hz=6.2`, `phase=1.43` |
| Canvas indication | PASS | Sine indication visible on note; 26 yellow indication columns detected |
| One-step undo | PASS | Undo removes vibrato (`null`) |
| One-step redo | PASS | Redo restores exact persisted values |
| Toolbar editor placement | PASS | Default toolbar popup remains within piano-roll wrap/viewport |
| Low-note context placement | FAIL | Popover overlaps automation lane by about 169px |
| Console/network health | PASS | No browser console errors; no network failures |

## Critical-user notes

- The editor is understandable and the disabled-state semantics are clear: sliders are unavailable until Enable is checked.
- The sine indication is present and parameter-responsive, but visually subtle at the default row height. It is still legible enough to confirm that vibrato exists.
- The context-menu placement behavior is the main usability issue. A professional editor should flip upward or clamp the popup inside the piano-roll/editor surface rather than covering the automation tabs/lane.

## Artifacts

- `vibrato_qa_results.json` — structured pass/fail evidence
- `browser_console.jsonl` — empty console/network health log
- `01_note_drawn_vibrato_tool_enabled.png`
- `02_context_menu.png`
- `03_vibrato_editor_context_low_note.png` — overlap defect evidence
- `04_vibrato_editor_adjusted.png`
- `05_vibrato_indication_after_close.png`
- `06_after_undo_no_vibrato.png`
- `07_after_redo_vibrato_restored.png`
- `08_vibrato_editor_toolbar_open.png`
