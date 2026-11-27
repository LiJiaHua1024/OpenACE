# Project Manager Browser QA

## Verdict

Focused project manager QA passed in real visible Chrome at exact `1272×837`. No implementation defects were found in the tested revision, including the click-outside backdrop delta.

## Evidence summary

- Transport with new `Projects` button: `scrollWidth=1272`, `clientWidth=1272`, overflow `0`.
- Popover listed recent projects with date, track count, and BPM metadata. Examples: `PM Gamma QA · 3 tracks · 150 BPM`, `PM Alpha QA · 1 tracks · 120 BPM`, `PM Beta QA · 2 tracks · 90 BPM`.
- Search `Beta` reduced the list to exactly `PM Beta QA`.
- Opening `PM Beta QA` updated the workspace title, BPM `90`, and two tracks.
- Copying non-current `PM Gamma QA` opened `PM Gamma QA Copy` with BPM `150` and all `3` tracks.
- Deleting non-current original `PM Gamma QA` removed it while current `PM Gamma QA Copy` stayed open unchanged.
- Clicking outside in the arrangement closed the popover.
- Deleting current `PM Gamma QA Copy` fell back to `PM Alpha QA` exactly once: one detail GET, zero create posts, one delete request; title remained stable across samples at `0.29s`, `1.1s`, `1.91s`, and `2.72s`.
- Final cache-busted reload: no console messages, no network failures, no body overflow, transport overflow `0`.

## Files

- `00_popover_metadata.png`
- `01_search_beta.png`
- `02_opened_beta.png`
- `03_gamma_copy_opened.png`
- `00_before_delete_noncurrent.png`
- `01_after_delete_noncurrent.png`
- `04_outside_click_closed.png`
- `02_after_delete_current_fallback.png`
- `03_final_layout.png`
- `project_manager_results.json`
