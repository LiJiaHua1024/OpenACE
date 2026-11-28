# Project operations QA report

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, fixture backend, rebuilt frontend.

## Result

Functional duplicate/delete flow passed, but one visual defect was found: the duplicate icon does not render recognizably as `⧉`; it appears as a plain hollow missing-glyph rectangle.

## Functional verification

Starting project:

- id `project_5215f322a228`
- title `Project Ops`

Clicked the visible duplicate project action.

Passed:

- duplicate opened in the UI
- duplicate id `project_57f7d9befaff` differed from the source id
- duplicate title exactly `Project Ops Copy`
- selector contained `Project Ops Copy`
- backend project list contained the persistent copy

Clicked the visible delete project action and accepted the browser confirmation.

Passed:

- confirmation text: `Delete project “Project Ops Copy”? This cannot be undone.`
- UI fell back to the original project `project_5215f322a228` / `Project Ops`
- `Project Ops Copy` disappeared from the selector
- copy id disappeared from the backend project list
- no console errors or network failures occurred

## Visual defect

The duplicate button glyph is not legible as the intended `⧉` overlapping-squares icon. In the high-resolution crop it is a plain hollow rectangular missing-glyph shape.

Evidence: `transport_actions_crop8x.png`.

This does not block functionality because the button remains clickable and has a tooltip, but it fails the visible-icon quality expectation.

## Evidence

- `01_before_duplicate.png`
- `02_after_duplicate.png`
- `03_after_delete.png`
- `transport_actions_crop8x.png`
- `project_operations_results.json`
