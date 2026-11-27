# Final Arrangement Wheel Isolation Regression

Real visible Chrome, exact `1272×837`, rebuilt/cache-busted frontend, 9-lane fixture.

All requested checks passed:

- Ctrl+wheel zoomed timeline while `scrollTop` remained fixed; zero passive-listener/console errors.
- Shift+wheel moved horizontally while `scrollTop` remained fixed.
- Plain wheel retained native vertical lane scrolling without horizontal redraw.
- Bottom lane names rendered in the arrangement label column and remained orienting while scrolled.
- Four-lane project remained unchanged/unscrollable at `166px` with zero scroll range.
- No layout overflow, console errors, HTTP errors, or unexpected network failures.

Recording: `/home/ubuntu/screencasts/arrangement-wheel-isolation-final/arrangement-wheel-isolation-final-edited.mp4`  
Machine evidence: `arrangement_vertical_scroll_fix_regression.json`  
Screenshots: `regression_00` through `regression_03`
