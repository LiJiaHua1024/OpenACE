# Arrangement Multi-Clip Selection/Editing QA Report

## Scope and environment

- Focused QA of the uncommitted arrangement multi-clip selection/editing behavior.
- Real visible Chrome at exactly `1272×837` through Playwright mouse interactions.
- Frontend rebuilt and cache-busted before testing.
- Backend schema unchanged; no backend restart was required.
- Fixture project: `project_af15424e895a`.
- Fixture arrangement: three valid audio clips across two tracks:
  - `MS Audio A`: `A1` at 480 ticks, `A2` at 1920 ticks
  - `MS Audio B`: `B1` at 960 ticks
- No implementation files were modified.

## Results

| Test | Result | Evidence |
|---|---:|---|
| Single click selects one clip with white outline | PASS | `canvaszoom_01_single_selected.png`, `16_retest_single.png` |
| Ctrl-click adds a clip on another track | PASS | `17_retest_ctrl_add.png` shows `A1` and `B1` selected while `A2` remains unselected |
| Marquee over empty arrangement selects intersecting clips across tracks | PASS | `19_retest_marquee_selected.png` shows `A1` and `B1` selected, not `A2` |
| Additive Ctrl marquee preserves existing selection and adds another clip | PASS | `canvaszoom_25_final_additive_marquee_selected.png` shows `A1`, `B1`, and `A2` all white-outlined |
| Dragging any selected clip group-moves all selected clips by the same quantized delta | PASS | Initial `(A1,A2,B1)=(480,1920,960)` became `(720,2160,1200)`, a uniform quantized `+240` tick delta |
| Group drag preserves relative positions and track membership | PASS | The `A1→B1` offset remained `480` ticks and `A1→A2` remained `1440` ticks; no clip changed tracks |
| Group drag clamps at zero as a group | PASS | Final clamped positions were `(A1,A2,B1)=(0,1440,480)`, preserving all relative offsets while minimum start hit zero |
| Trim affects only the target clip | PASS | Right trim changed only `A1` duration `960→840`; other positions/durations were unchanged |
| Fade affects only the target clip and does not group-move | PASS | Fade-in edit set exactly one clip (`A2` in the final probe) to `fade_in_ticks=120`; starts/durations of all clips were unchanged |
| Multi-selection duplicate shifts by group span | PASS | Selected originals at starts `120/600/1440` duplicated to `2400/2880/3720`, a uniform group-span shift of `2280` ticks on the original tracks |
| Multi-selection delete removes all selected clips | PASS | Clip count changed from 6 to 3; all three duplicated selected clips were removed |
| Undo/redo works for group delete | PASS | Undo restored 6 clips with the same IDs; redo returned to 3 clips |
| Multi-selection copy/paste at cursor preserves spacing and original tracks | PASS | Originals `120/600/1440` pasted as `2520/3000/3840`; offsets `+480` and `+1320` preserved, with A clips on track A and B clip on track B |
| Exact `1272×837` layout | PASS | `body scrollWidth=clientWidth=1272`; arrangement canvas `scrollWidth=clientWidth=714` |
| Console/network health | PASS | Final cache-busted reload produced zero console messages, zero network failures, and zero HTTP errors |

## Quantitative operation evidence

### Group drag and clamp

```json
{
  "initial": {"A1": [480, 960], "A2": [1920, 960], "B1": [960, 960]},
  "after_group_drag": {"A1": [720, 960], "A2": [2160, 960], "B1": [1200, 960]},
  "after_clamp": {"A1": [0, 960], "A2": [1440, 960], "B1": [480, 960]}
}
```

### Duplicate

Original selected group starts: `A1=120`, `B1=600`, `A2=1440`.

Duplicated group starts: `A1=2400`, `B1=2880`, `A2=3720`.

The uniform shift is `2280` ticks, matching the selected group span in the mutated fixture state (`min start 120`, `max end 2400`).

### Delete / undo / redo

- Before delete: 6 clips.
- After delete: 3 clips.
- After undo: same 6 clips restored, including the same clip IDs.
- After redo: same 3 clips again.

### Copy / paste

Original spacing relative to `A1=120`:

- `B1-A1 = 480`
- `A2-A1 = 1320`

Pasted positions:

- `A1=2520` on `MS Audio A`
- `B1=3000` on `MS Audio B`
- `A2=3840` on `MS Audio A`

Pasted spacing:

- `B1-A1 = 480`
- `A2-A1 = 1320`

Track membership and durations were preserved.

## Harness notes

Two early interaction attempts were harness aiming artifacts, not implementation defects:

1. A fade drag aimed at an exact boundary initially trimmed rather than faded in one run. A controlled final probe at the exact `A2` left boundary (`x=512`, top fade strip) correctly produced `fade_in_ticks=120`, so fade creation works.
2. One additive-marquee attempt began inside the edge/fade hit zone or outside the canvas, so no valid marquee was created. Re-aiming at genuinely empty arrangement space produced the correct additive selection. The final visual proof is `canvaszoom_25_final_additive_marquee_selected.png`.

The fixture was reset to the canonical three-clip arrangement after the mutation tests; final health checks therefore show the canonical positions again.

## Defects

No implementation defects were confirmed in this focused test.

## Key evidence files

- `canvaszoom_01_single_selected.png` — single white clip selection
- `17_retest_ctrl_add.png` — Ctrl additive cross-track selection
- `canvaszoom_19_retest_marquee_selected.png` — non-additive marquee result
- `canvaszoom_25_final_additive_marquee_selected.png` — additive marquee result with all three clips selected
- `05_group_drag_held.png` — group drag in progress
- `08_after_duplicate.png` — duplicated group
- `09_after_group_delete.png` — selected duplicated group removed
- `10_after_undo_delete.png` — undo restored group
- `11_after_redo_delete.png` — redo removed group again
- `14_after_group_paste.png` — paste result in visible range
- `26_final_layout_canonical.png` — final canonical layout/health state

Recording: `/home/ubuntu/screencasts/arrangement-multiselect-qa/arrangement-multiselect-qa-edited.mp4`
