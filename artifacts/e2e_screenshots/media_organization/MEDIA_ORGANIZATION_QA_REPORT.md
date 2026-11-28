# Media organization QA

Real visible Chrome 1272×837; rebuilt frontend/backend restarted; repo code unchanged.

Passed: upload appeared in media bin; Tags prompts assigned `warm,vocal chop` and folder `references/pop`; chips displayed; folder filter and All folders worked; search matched tag/folder/name; reload/SSE persisted metadata; overlong tag was rejected readably (`media tags must be at most 40 characters`) without overwriting existing metadata; partial API PATCH preserved folders; clearing both prompt values removed metadata; Add at playhead created second track and one clip; deleting in-use media was correctly blocked with 409. Layout appeared contained. Only console/network error was the intentional 422 validation rejection.

Incomplete/negative: drag-from-media-bin regression was not tested. File deletion cleanup could not be completed because my approximate UI click did not select/remove the arrangement clip (`clips_after_ui_delete=1`), so the target media remained in use and `media_removed=false`. The observed `sidecar_removed=true` is therefore not valid proof of delete cleanup because metadata had already been cleared in the prior clearing test. This portion must be retested.

Evidence: `media_organization_results.json`, screenshots `01_uploaded.png` through `05_deleted.png`.

## Focused drag/delete retest

Passed. Dragging valid media onto arrangement created one clip on accompaniment track index 1 at tick 480. Right-clicking the clip and choosing exact `Delete` removed it; backend clips became zero. A fresh unused unique media upload was then tagged `retag`, foldered `reftest`, deleted through the media-row UI, disappeared from `/api/media`, and its key was absent from `data/uploads/media_metadata.json`. Evidence: `06_drag_created.png`, `07_clip_menu.png`, `08_media_deleted.png`, JSON keys `focused_drag_delete_retest` and `focused_delete_unused_media_retest`.
