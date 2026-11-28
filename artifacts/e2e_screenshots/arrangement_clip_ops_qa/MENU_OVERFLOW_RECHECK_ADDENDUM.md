# Arrangement menu overflow recheck addendum

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, backend restarted from the current tree and frontend rebuilt before testing.

## Result

The focused recheck found that the menu overflow is **not fully fixed**.

### Remaining defect: full clip menu still overflows

At a bottom/right clip target, the full clip menu measured:

- menu: `204 × 208px` at screen `(742,62)`
- arrangement canvas: `714 × 132px` at screen `(236,58)`
- right edge: 4px inside the arrangement
- bottom edge: **80px below the arrangement strip**

The menu is still laid out as a single column. Computed style evidence:

```text
display: flex
flex-direction: column
width: 204px
grid-template-columns: 1fr 1fr (present but ineffective because display is flex)
```

Likely root cause: `.arrangement-context-menu` is defined before `.piano-context-menu` in `frontend/src/styles.css`. Both selectors have equal specificity, so the later `.piano-context-menu { display:flex; flex-direction:column; ... }` rule overrides the arrangement menu's `display:grid`. Because the real menu remains 208px tall while the clamp calculation assumes 126px, it is clamped to the wrong height and spills 80px into the piano-roll area.

Visual evidence: `evidence_menu_overflow_recheck_montage.png`.

### Passed checks

- Empty-space paste menu measured `204 × 40px` and stayed inside the arrangement strip:
  - right edge 4px inside
  - bottom edge 2px inside
- Paste at cursor remained enabled after Copy and successfully pasted a preserved clip at tick `2760`.
- Split at cursor, Duplicate, and Delete all remained clickable; each mutation was undone correctly.
- Clip gain input remained visible/focusable/clickable.
- No console errors or network failures occurred.

## Artifacts

- `menu_recheck_01_full_menu_bottom_right.png`
- `menu_recheck_03_gain_focused.png`
- `menu_recheck_04_empty_paste_bottom_right.png`
- `menu_recheck_05_after_empty_paste.png`
- `evidence_menu_overflow_recheck_montage.png`
- `menu_overflow_recheck_results.json`
