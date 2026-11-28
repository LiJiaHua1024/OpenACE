# SVC Render Job Key-Card Recheck

Date: 2026-11-28  
Build: `index-lJk_TVei.js`  
Implementation modified: no

## Verdict

Passed. A freshly completed manual `-3` SVC job card visibly displayed exact key text `key: -3 semitones` without layout overflow.

## Evidence

- Job: `job_e52c58ce2bbd`, completed, exact backend fields `pitch_shift=-3`, `auto_shift=false`.
- Job-card key text: `key: -3 semitones`.
- Card width geometry: `scrollWidth=285`, `clientWidth=285`; no horizontal overflow.
- Key text box stayed inside card bounds.
- Conversion controls regression passed:
  - Auto mode hid manual semitone input.
  - Re-selecting manual restored input.
  - Negative value `-2` remained typeable after reselecting.
- Console errors/warnings: zero.
- Failed browser network responses: zero.

## Artifacts

- `svc_job_keycard_manual_minus3.png`
- `svc_jobcard_recheck_results.json`
