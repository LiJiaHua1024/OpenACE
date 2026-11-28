# Autosave status/failure recovery QA

Real visible Chrome 1272×837, rebuilt frontend/restarted backend, fresh project `project_f86589135e09`; repo code unchanged.

Passed:
- Normal title edit status sequence exactly included `Saved → Saving… → Saved`; backend title `Autosave Alpha`.
- Rapid edits produced `Saved → Saving… → Saved`, exactly one debounced PUT, final backend title `Rapid 123456789`; no duplicate/racing status regression.
- With PUTs intercepted/aborted, edit produced persistent compact `Save failed — retry`; tooltip/error detail `Failed to fetch`; top error `save failed: Failed to fetch`.
- Retrying while still blocked remained in error.
- Ctrl+Z and Ctrl+Y under blocked network also surfaced `Save failed — retry` rather than being swallowed.
- After removing interception, clicking retry produced `Saving… → Saved`; backend persisted latest title `Blocked Latest`.
- Browser reload showed title `Blocked Latest` and state `Saved`.
- Save button remained inside header at x765 width45; no save-button toolbar overflow. Full compact label visible in screenshot.
- Network errors were only the two intentional aborted PUT resource entries (`net::ERR_FAILED`); no HTTP >=400 and no unexpected console errors.

Evidence: `autosave_status_results.json`; screenshots `01_saved.png`, `02_save_failed.png`, `03_recovered.png`, `04_reload.png`.
