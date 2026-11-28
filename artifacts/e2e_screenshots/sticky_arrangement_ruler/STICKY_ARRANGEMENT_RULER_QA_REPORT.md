# Sticky Arrangement Ruler Focused Browser QA

Real visible Chrome, exact `1272×837`, rebuilt/cache-busted frontend, 9-lane fixture. Implementation unchanged.

All requested checks passed:

- Large viewport/content sizing correct: viewport `210px`, content/canvas `336px`.
- Ctrl+wheel zoomed timeline while `scrollTop` stayed fixed; no passive listener errors.
- Shift+wheel and horizontal wheel delta moved horizontally while `scrollTop` stayed fixed.
- Plain wheel retained native vertical lane scrolling without horizontal movement.
- Ruler remained stuck at the visible viewport top while scrolled; bar-number overlay was drawn at content y `scrollTop+16`.
- Bottom lane names `Sticky Lane 8/9` rendered in the arrangement label column and remained orienting while scrolled.
- Clicking the sticky ruler sought to the correct musical position `1.4.1` rather than selecting/dragging the underlying lane.
- Four-lane project remained unchanged/unscrollable at `166px` with zero scroll range.
- Layout, console, network, and HTTP were clean; only expected `/api/events` navigation aborts appeared.

Note: the wall-clock time at `1.4.1` is affected by the fixture's tempo map, so the musical ruler position was used as the correct tempo-independent assertion.

Recording: `/home/ubuntu/screencasts/sticky-arrangement-ruler-qa/sticky-arrangement-ruler-qa-edited.mp4`  
Machine results: `sticky_arrangement_ruler_results.json`  
Key screenshots: `00_scrolled_sticky_ruler_bottom_names.png`, `01_sticky_ruler_click_seek.png`, `02_small_project_unchanged.png`
