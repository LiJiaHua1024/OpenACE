# Arrangement menu overflow recheck 2 addendum

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, backend restarted from the current tree and frontend rebuilt before testing.

## Result

The grid-layout fix is now effective, but the full-menu clamp is still **2px too small** at bottom/right placement.

## Measurements

### Full clip menu

At a bottom/right clip target:

```text
menu:   204 × 130px at screen (742,62)
canvas: 714 × 132px at screen (236,58)
right overflow:  -4px  (inside)
bottom overflow: +2px  (still overlaps piano roll)
```

Computed style:

```text
display: grid
grid-template-columns: 96.3594px 93.6406px
width: 204px
height: 130px
```

The menu is now visibly two-column and compact. Buttons are readable and do not collide with the sidebar horizontally. However, because the implementation clamps using an estimated full-menu height of 124px while the real menu measures 130px, the bottom border still spills 2px into the piano-roll area.

### Empty-space paste menu

```text
menu: 204 × 40px
right overflow:  -4px  (inside)
bottom overflow: -2px  (inside)
```

The paste menu remains fully inside the arrangement strip.

## Behavioral checks

- Copy remained clickable.
- Paste at cursor remained enabled after Copy and pasted a preserved clip at tick `2760`.
- Duplicate, Split at cursor, and Delete all remained clickable; each mutation was undone correctly.
- Clip gain input remained visible, readable, focusable, and clickable.
- No console errors or network failures occurred.

## Evidence

- `evidence_menu_overflow_recheck2_montage.png`
- `menu2_recheck_01_full_menu_bottom_right.png`
- `menu2_recheck_03_gain_focused.png`
- `menu2_recheck_04_empty_paste_bottom_right.png`
- `menu2_recheck_05_after_empty_paste.png`
- `menu_overflow_recheck2_results.json`
