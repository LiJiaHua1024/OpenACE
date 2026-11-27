# Arrangement Vertical Scroll Fix Regression Addendum

Date: 2026-05-15  
Surface: real visible Chrome, exact `1272×837`, rebuilt/cache-busted frontend

## Result

The Ctrl+wheel defect is **not fixed**. Ctrl+wheel still vertically scrolled the arrangement (`scrollTop 60 → 127`) while zooming the timeline (bar spacing `403.2px`). Chrome also emitted two console errors:

`Unable to preventDefault inside passive event listener invocation.`

Thus the new `preventDefault()` calls are ineffective in the React/passive wheel path and introduce console errors.

Passed checks:

- 9-lane viewport/content sizing: viewport `210px`, content/canvas `336px`.
- Shift+wheel moved the timeline horizontally while `scrollTop` stayed `60`.
- Plain wheel still scrolled vertically (`scrollTop >100`) without horizontal redraw.
- Bottom lane names `Fix Scroll Lane 8` and `Fix Scroll Lane 9` rendered at arrangement label-column x=8 and were visible while scrolled.
- Correct four-lane project remained unchanged/unscrollable at `166px`, `scrollTop=0`, no scroll range.
- No layout overflow or HTTP errors. Network failures were only expected `/api/events` reload aborts.

Files:

- Recording: `/home/ubuntu/screencasts/arrangement-scroll-fix-regression/arrangement-scroll-fix-regression-edited.mp4`
- Machine results: `arrangement_vertical_scroll_fix_regression.json`
- Screenshots: `regression_00` through `regression_03`
