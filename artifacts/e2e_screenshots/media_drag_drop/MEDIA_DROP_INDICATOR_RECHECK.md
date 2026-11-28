# Media-drop indicator regression recheck

Date: 2026-11-27  
Surface: real visible Chrome, exact CSS viewport `1272x837`  
Input: real native HTML5 drag initiated with CDP/Playwright mouse input  
Implementation files: unchanged

## Verdict

The child-traversal fix improves the previously failing accompaniment-lane diagonal drag: the cyan insertion indicator now remains visible immediately before drop and clears after drop. Leaving the arrangement without dropping also clears it correctly without mutating the project.

However, the regression is **not fully fixed**: the Alt fine-placement diagonal drag still loses/hides the indicator immediately before drop, even though the drop succeeds at the correct nonsnapped tick.

## Exact results

### Initial empty diagonal control

- pre-drop indicator: left `176px`, top `58px`, height `34px`, cyan `rgb(103, 232, 249)`
- post-drop indicator: `null`
- placement unchanged: new audio clip `start=480`, `duration=1920`

### Accompaniment diagonal regression

- pre-drop indicator: left `400px`, top `92px`, height `34px`, cyan
- post-drop indicator: `null`
- accompaniment clip placed correctly in existing BGM lane: `start=1440`, `duration=1920`
- no extra track created

This specific previous failure is fixed.

### Alt fine diagonal regression

- pre-drop indicator: **`null`**
- post-drop indicator: `null`
- placement still correct: new audio clip `start=600`, `duration=1920`
- `600` is nonsnapped, so Alt placement itself is correct

The Alt indicator failure therefore remains. A supplemental steady-position probe shows the indicator can appear at the correct Alt position (`left204px` vs normal `left176px`) when the drag is moved within the arrangement in a controlled path, so this remains path/interaction dependent rather than a total Alt failure.

### Leave without dropping

- indicator inside arrangement: present at left `400px`, top `24px`
- after moving outside arrangement while still dragging: `null`
- mouse release outside arrangement did not mutate project
- track count stayed `4 -> 4`

### Console/network

No console errors/warnings or failed network responses.

## Defect remaining

**Alt fine lower-arrangement diagonal drags can still lack visible insertion feedback immediately before drop.** The drop result is correct, but the user may not see where the clip will land.

## Artifacts

- `media_indicator_recheck.json`
- `media_indicator_recheck.log`
- `alt_lower_probe.json`
- `20_recheck_initial_empty_indicator.png`
- `21_recheck_accompaniment_indicator.png`
- `22_recheck_alt_indicator.png`
- `23_recheck_after_leave.png`
