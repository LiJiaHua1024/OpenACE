# Arrangement Vertical Scroll Focused Browser QA

Date: 2026-05-15  
Surface: real visible Chrome through Playwright/CDP, exact viewport `1272×837`  
Frontend: rebuilt and cache-busted; implementation unchanged by QA  
Large fixture: 9 lanes, bottom clips on lanes 8/9

## Result

Core vertical scrolling and bottom-lane editing passed, but one wheel-routing defect was confirmed: **Ctrl+wheel zoomed the timeline and also natively scrolled the arrangement lanes**, producing double-scroll behavior. A separate usability concern is that the left track list does not visually follow the scrolled arrangement lanes.

## Confirmed defect

### Ctrl+wheel double-scroll

With arrangement scrollTop positioned at `60`, Ctrl+wheel changed the zoomed bar spacing to about `403.2px` as expected, but arrangement scrollTop also changed `60 → 127`. Browser zoom remained `1`, so this was not browser zoom. Ctrl+wheel should zoom the timeline without also vertically scrolling lanes.

## Evidence summary

- Large 9-lane project content height was `336px`; arrangement viewport capped at `210px`; canvas height was `336px`.
- Plain wheel scrolled natively to the bottom (`scrollTop > 100`) without any horizontal timeline redraw.
- Bottom lane clip was visible at scrolled position and clickable using correct content coordinates.
- Bottom clip drag by `+28px` changed start `600 → 720` ticks as expected; undo restored `600`.
- Context menu at scrolled bottom position was fully inside the viewport (`y 136–263` within arrangement viewport `58–268`).
- Copy/paste at scrolled bottom position created exactly one new bottom-lane clip (`clip_8a823750-664`).
- Delete removed that pasted clip; undo restored it.
- Shift+wheel and horizontal wheel delta horizontally moved the timeline while vertical scrollTop remained fixed at `60`.
- Ctrl+wheel zoomed the timeline, but also vertically scrolled the arrangement — defect above.
- Corrected small four-lane recheck measured arrangement/content/canvas height `166px`, `scrollTop=0`, `scrollHeight=166`, `clientHeight=165`; no scroll range.
- No horizontal layout overflow. Console messages `0`; HTTP errors `0`; network failures were only expected `/api/events` aborts from intentional reloads.
- Additional UX concern: after arrangement scrolling, bottom arrangement rows appear beside unrelated upper rows in the left track list because the track list does not scroll in sync.

## Harness note

The first small-project check in `arrangement_vertical_scroll_results.json` was invalid because repeated harness attempts caused the backup fixture itself to be overwritten with the 9-lane project. A corrected four-lane recheck was then run and passed; use `small_project_recheck.json` and `11_small_project_unscrollable.png` as the valid small-project evidence.

## Files

- Recording: `/home/ubuntu/screencasts/arrangement-vertical-scroll-authoritative/arrangement-vertical-scroll-authoritative-edited.mp4`
- Machine results: `arrangement_vertical_scroll_results.json`
- Corrected small-project results: `small_project_recheck.json`
- Key screenshots:
  - `00_large_project_top.png`
  - `03_bottom_lane_visible.png`
  - `05_bottom_clip_drag_held.png`
  - `07_bottom_context_menu.png`
  - `08_bottom_clip_pasted.png`
  - `11_small_project_unscrollable.png`
