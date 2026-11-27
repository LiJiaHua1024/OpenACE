# Project folder organization QA

Environment: real visible Chrome over CDP at exact CSS viewport `1272×837`, backend restarted in fixture mode, frontend rebuilt/cache-busted. Used four isolated QA projects, real Projects-popover UI editing/filtering/search/open/copy/delete interactions, backend API exactness checks, external SSE-triggering PATCHes, reloads, CLI invocation, direct MCP function invocation, and geometry measurements. No implementation files were modified.

## Confirmed defect

### Filtered/search-empty project list does not show the required empty state

With search `zzzz-no-such-folder`, the row count is `0`, but `.project-manager-list .empty-state` count is also `0`; the popover is simply blank. Expected: `No projects`.

Evidence: `10_empty_state_defect.png` and `folder_ui_supplement.json`.

Likely implementation cause: the JSX empty-state condition uses the unfiltered `props.projects.length`, not the filtered row count.

## Spec ambiguity / exact behavior

`PATCH /api/projects/{id}/organization` with JSON string `"folders":"CommaA, CommaB"` returns `422` because the request schema requires a list. Legacy stored metadata containing comma-string folders is normalized correctly in `/api/projects` summaries. If the requirement intended the organization PATCH itself to accept comma strings, this is a second backend defect; if comma-string support was only for legacy metadata/CLI normalization, current behavior is consistent.

Exact 422 response is preserved in `project_folders_results.json`.

## Passed coverage

- Exact viewport `1272×837`.
- Inline folder editor Escape cancels without writing.
- Inline Save writes exact `['Experiments','SharedLab']` to backend JSON.
- Rows display `▸Experiments ▸SharedLab`.
- Removing a folder persists exact remaining `['SharedLab']`.
- External organization PATCH while popover remains open updates row and filter options through SSE without reopening popover.
- Folder filter `SharedLab` includes Alpha+Beta and excludes Zeta; All restores.
- Search by folder text matches Alpha through `Experiments`.
- Backend normalization list input trims, dedupes, drops blanks, caps at 8.
- 60-character folder truncates to exactly 48 chars.
- Legacy comma-string metadata normalizes in summaries (`LegacyA`,`LegacyB`).
- Reload persists folder metadata and row annotations.
- Duplicate copies folders but is unpinned.
- Pin-first ordering remains intact.
- Project open, copy, delete, and fallback still work.
- CLI `--folders` works and dedupes: `['CLI One','CLI Two']`.
- MCP `organize_project` works and dedupes: `['MCP One','MCP Two']`.
- Normal and 48-character folder rows have no button overlap; popover remains within viewport; transport/body have no horizontal overflow.
- Console, network, and HTTP are clean.

## Artifact index

- `00_two_folder_assignment.png`
- `01_sse_folder_update_popover_open.png`
- `02_shared_folder_filter.png`
- `03_empty_state.png` (from incomplete first harness pass)
- `04_reload_folder_persistence.png`
- `05_duplicate_folder_unpinned.png`
- `06_delete_fallback_after_folder_copy.png`
- `07_folder_layout_rows.png`
- `08_corrected_shared_filter.png`
- `09_search_by_folder.png`
- `10_empty_state_defect.png`
- `11_long_folder_layout.png`
- `project_folders_results.json` — raw matrix, including harness false negatives later corrected
- `folder_ui_supplement.json` — corrected filter/search/empty-state evidence
- `sse_supplement.json`
- `long_folder_layout_supplement.json`
- `cli_mcp_supplement.json`
