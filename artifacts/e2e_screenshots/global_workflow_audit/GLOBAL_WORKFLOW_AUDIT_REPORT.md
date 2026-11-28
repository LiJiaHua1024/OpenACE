# Global Workflow Audit Report

Commit under test: `b245eb7 Implement automation point dragging` on `devin/1795696369-dynamic-expression`. Backend was restarted with the CI synthesis fixture and the production frontend was rebuilt/cache-busted. Testing used visible Chrome at a 1600×1035 CSS viewport against the realistic project `project_c4bccc903fcc` / **Global Workflow Audit** containing vocal notes/lyrics/manual phonemes/vibrato/pitch curve, a rendered vocal, audio clips with trims/fades/gain, volume/pan/dynamic/pitch automation, breath data, uploaded media, a tempo point, and a persisted loop.

No implementation files were modified or committed.

## Highest-ROI findings

### P1 — Reload does not restore the current project; it silently opens the first pinned project

**Repro:** open **Global Workflow Audit**, reload the browser, observe the project selector/title.

**Observed:** the app opened pinned **FolderQA Beta** instead of the audit project. Evidence: `02_after_reload_wrong_project.png`. This is not merely cosmetic: after a reload the user can edit the wrong project without any interstitial warning.

**Expected:** remember and restore the last-open project ID across reload, or at minimum make the pinned-project boot behavior explicit.

### P1 — Transport bar overflows even at 1600 px; Import audio is clipped and there is no horizontal escape

**Repro:** open any project at a 1600×1035 viewport and inspect the right end of the transport bar.

**Observed exact geometry:** `Import audio` left `1551.66`, right `1610.58`, viewport width `1600`; `document.body.scrollWidth` remains `1600`, so the control is clipped with no horizontal scrolling. Evidence visible in `00_audit_project_overview.png`, `08_pitch_handle_created.png`, and most full-screen captures.

**Impact:** a core import control is partially inaccessible even on a wide desktop viewport; narrower laptops are worse.

### P1 — Media-bin drag ignores the shared musical snap grid

**Repro:** set piano-roll Grid to `1/32`, drag `steady440_20.wav` from Media bin onto the arrangement at raw tick ≈330, inspect backend clips.

**Observed:** the created clip started exactly at `480` ticks (quarter note), not the expected nearby 60-tick increment (`360`). The arrangement currently hard-codes media-drop snapping to `ppq` rather than `snapGrid`. Backend state after the test contained two media-created clips both at `start_ticks=480`; one was the deliberate playhead placement and the second was the drag. Evidence: `15_after_media_drag.png` and `global_audit_results.json`.

**Impact:** media placement disagrees with the snapping behavior of clip/note/tempo/automation editing and misplaces audio in normal use.

### P1/P2 — Newly added tracks are not selected

**Repro:** with **Lead Vocal** selected, click `+ Vocal`.

**Observed:** `Vocal 3` appeared, but **Lead Vocal** remained the selected/editing track. Evidence: `04_add_track_selection.png`. The render panel and piano roll therefore continue targeting the old track, making it easy to edit or render the wrong track immediately after creation.

**Expected:** select the newly created track, consistent with most DAWs.

### P2 — Ctrl+Shift+Z does not redo

**Repro:** change time signature to 3/4, press Ctrl+Z, then Ctrl+Shift+Z; inspect backend.

**Observed exact sequence:** after undo `{numerator:4,denominator:4}`; after Ctrl+Shift+Z still `{numerator:4,denominator:4}`; after Ctrl+Y `{numerator:3,denominator:4}`. Evidence: `20_redo_shortcut_probe.png` and `global_audit_finish_results.json`.

**Impact:** only Ctrl+Y works. Ctrl+Shift+Z is the dominant redo shortcut in many creative applications and should be accepted as an alias.

### P2 — Escape does not close the Project manager overlay

**Repro:** click **Projects**, type in the search field, press Escape, then try to click a track.

**Observed:** the transparent `.project-manager-backdrop` remained active and intercepted pointer events; a follow-up UI probe timed out because that backdrop covered the track list. Clicking outside does close it, but Escape does not. Evidence: `24_project_search.png` plus probe failure recorded during the audit.

### P2 — Media-bin “Add at playhead” always creates another audio track instead of using the selected audio track

**Repro:** select the existing **Reference Audio** track, use Media bin → **Add at playhead**.

**Observed:** a new `Audio — steady440_20` track was created. Repeating/dragging created another identically named track, leaving multiple indistinguishable truncated track names. Evidence: `14_media_added.png` and `15_after_media_drag.png`. This differs from **Import audio as clip at playhead**, which does target the selected non-vocal track.

## Major workflows that passed

- **Project creation:** `+ New` opened an editable untitled project with a default Lead Vocal track; evidence `01_new_project_blank_workspace.png`.
- **Project manager organization:** popover, search, pin/tag/folder/copy/delete controls rendered; search for `audit` found the audit project with its `#audit #demo` tags and `qa` folder; evidence `03_project_manager.png`, `24_project_search.png`.
- **Piano-roll editing:** note selection, lyric editing (` audit_n2` became `嘿`), manual phoneme override (`x ei`), vibrato editor, and targeted per-note pitch-handle creation all worked. The targeted pitch probe added `{offset_ms:250, cents:3}` and undo removed it. Evidence `05`–`08`, `25`.
- **Automation surface:** Breath/Dynamic/Pitch/Air/Falsetto/Tension/Energy/Volume/Pan tabs were visible; prepopulated volume/pan/dynamic curves redrawn and persisted. Evidence `11_volume_automation.png`, `12_pan_automation.png`.
- **Arrangement editing:** clip drag moved `rendered fixture A` by exactly +28 px (=120 ticks at 112 px/beat) and undo restored it; context menu and duplicate were reachable and undoable. Evidence `09_clip_drag.png`, `10_arrangement_menu.png`.
- **Transport seek/play/loop:** seeking to loop start showed `1.2.1 / 00:00.50`; after 2.2 seconds of looped playback the transport was back near loop start at `1.2.2 / 00:00.69`, demonstrating loop wrap rather than linear runaway. Evidence `23_transport_loop_probe.png`.
- **Tempo/time signature/grid:** tempo map rendered; time-signature change persisted and undo/redo behavior was exact when using Ctrl+Y.
- **Render jobs:** `Render vocal` created completed fixture job `job_96ab302e0712`, output `/home/ubuntu/repos/OpenACE/data/renders/project_c4bccc903fcc/job_96ab302e0712/vocal.wav`; stale-render warning cleared. Evidence `21_render_job_completed.png`.
- **Export:** WAV download succeeded as `Global Workflow Audit.wav`, 6,021,860 bytes. Evidence `22_export_wav.png` and `master_audit.wav`.
- **Console/page/network errors:** none observed in the completed instrumented continuation.

## Test-process note

The first broad audit script stopped when it attempted to click **Render vocal** while an audio track was selected; the button was correctly disabled because audio tracks have no notes. I corrected the test setup by selecting the vocal track and completed render/export verification. This was a test-sequence issue, not a product failure.

## Artifact index

- Recording: `/home/ubuntu/screencasts/global-workflow-audit/global-workflow-audit-edited.mp4`
- Combined results: `global_audit_results.json`
- Continuation instrumentation: `global_audit_finish_results.json`
- Downloaded master: `master_audit.wav`
- Key evidence screenshots: `00`–`25` in this directory plus `contact_sheet.jpg`
