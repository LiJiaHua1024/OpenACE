# Project folder fix regression recheck

Environment: real visible Chrome over CDP at exact CSS viewport `1272×837`; frontend rebuilt, backend fully restarted after correcting the initially stale process; cache-busted page load. No implementation files modified.

## Result

All requested regression checks passed.

- Impossible search `zzzz-no-such-folder`: `0` rows, exactly one project-list empty state, text `No projects`.
- Clearing search restored `4` FolderQA rows in the filtered harness state.
- Folder-filter impossible-state stress: selected sole `OnlyOne` folder (`1` row), externally removed that membership via PATCH while popover remained open; SSE updated UI to `0` rows and `No projects`.
- Resetting to all folders restored rows (`326` total projects in the shared local project store).
- Comma-string organization PATCH now succeeds with HTTP `200` and normalizes `" CommaA, CommaB,CommaA,,CommaC"` to `['CommaA','CommaB','CommaC']`.
- Layout exact `1272×837`; body and transport scroll/client widths are equal with no horizontal overflow.
- Console and network errors: none.

Evidence: `folder_fix_recheck.json`, `12_fixed_empty_state_search.png`, `13_fixed_empty_state_filter.png`.
