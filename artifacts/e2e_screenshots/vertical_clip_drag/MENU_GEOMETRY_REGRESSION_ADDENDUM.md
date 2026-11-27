# Context Menu Geometry Regression Addendum

Date: 2025-11-27  
Scope: dynamic arrangement-height clamp for arrangement context menus.  
Environment: real visible Chrome, exact `1272×837`, rebuilt/cache-busted frontend. No implementation files modified.

## Result: passed

| Check | Result |
|---|---:|
| Lane-2 menu clamp | PASS — click relative Y `109`; menu top `35`, bottom `162` inside `166px` arrangement |
| Lane-3 menu clamp | PASS — click relative Y `143`; menu top `35`, bottom `162` inside `166px` arrangement |
| Expected clamp | PASS — expected approximately `35` (`166 - 130 - 1`); measured exactly `35` |
| Menu fully inside arrangement | PASS — relative vertical range `35–162` within `0–166` |
| Visually close to click | PASS — click Y positions `109` and `143` are both inside the menu's vertical range |
| Copy clickable | PASS — Copy was visible, clicked, and menu closed |
| Delete clickable | PASS — Delete was visible/clicked and removed the lane-3 test clip |
| Exact layout | PASS — `1272×837`; body `1272/1272`; transport `1272/1272`; arrangement `166px` high with no horizontal overflow |
| Console/network/HTTP | PASS — zero console messages, zero network failures, zero HTTP errors |

Artifacts:

- Recording: `/home/ubuntu/screencasts/vertical-menu-geometry-final/vertical-menu-geometry-final-edited.mp4`
- Results JSON: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/vertical_menu_geometry_regression_results.json`
- Lane-2 menu screenshot: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/regression_menu_lane2_before_copy.png`
- Lane-3 menu screenshot: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/regression_menu_lane3_before_delete.png`
- After delete screenshot: `/home/ubuntu/repos/OpenACE/artifacts/e2e_screenshots/vertical_clip_drag/regression_menu_after_delete_lane3.png`
