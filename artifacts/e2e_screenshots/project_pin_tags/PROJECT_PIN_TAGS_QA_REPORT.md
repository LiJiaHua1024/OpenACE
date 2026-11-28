# Project Pinning/Tag Organization Focused Browser QA

Date: 2026-05-15  
Surface: real visible Chrome through Playwright/CDP, exact viewport `1272×837`  
Backend restarted; frontend rebuilt/cache-busted; implementation unchanged.

## Result

All requested focused checks passed. No project pinning/tag organization defect was confirmed.

## Evidence summary

- Created three deterministic projects: `PinTag QA Alpha` (oldest), `PinTag QA Beta`, `PinTag QA Gamma` (newest).
- Initial order was newest-first: Gamma, Beta, Alpha.
- Pinning Alpha moved it above the newer projects; backend metadata had `pinned: true`.
- Unpinning Alpha restored Gamma, Beta, Alpha order; backend metadata had `pinned: false`.
- Tag editor Escape closed a Beta draft without saving.
- Enter saved Beta tags with dedupe and 32-character truncation: `['betatag', 'abcdefghijklmnopqrstuvwxyzabcdef']`.
- Save button persisted Gamma's max-12 rule: `['gammatag', 'z1' … 'z11']`.
- Tags remained visible after reload and matched backend metadata.
- Searching `alphatag` isolated exactly the Alpha row.
- External backend organization PATCH updated the already-open popover through SSE: Gamma showed `★` and `#sse-tag` without reload.
- Duplicating pinned/tagged Alpha produced `PinTag QA Alpha Copy` with tags `['alphatag', 'shared']` but `pinned: false`.
- Normal row open opened Beta in the main title input.
- Non-current duplicate deletion removed the copy.
- Deleting current Beta fell back cleanly to another project.
- Popover measured `360px` wide at x `230`, fully inside the `1272px` viewport; rows `342/342`, popover `358/358`, and editor had no scroll/client width overflow.
- Console messages `0`; HTTP errors `0`; network failures were only expected `/api/events` aborts from intentional reloads.

## Files

- Recording: `/home/ubuntu/screencasts/project-pin-tags-qa/project-pin-tags-qa-edited.mp4`
- Machine results: `project_pin_tags_results.json`
- Key screenshots:
  - `00_initial_updated_order.png`
  - `01_alpha_pinned_first.png`
  - `02_tag_editor_open.png`
  - `04_search_by_tag_isolates.png`
  - `05_sse_metadata_update.png`
  - `06_duplicate_unpinned_tags.png`
  - `07_current_delete_fallback.png`
