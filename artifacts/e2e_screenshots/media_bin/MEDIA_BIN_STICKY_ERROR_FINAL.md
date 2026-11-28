# Media-bin sticky error final regression

Date: 2026-11-27  
Surface: real visible Chrome, exact CSS viewport `1272x837`  
Implementation files: unchanged

## Result: passed

The sticky error-banner regression is fixed. Reproducing used-media deletion from the media bin immediately showed the concise readable error at the bottom of the right sidebar without any manual scrolling after the delete click.

Exact immediate measurements after Delete:

- viewport: `1272x837`
- error text: `media file is used by arrangement clips in 1 project(s); remove those clips before deleting it`
- CSS position: `sticky`
- CSS bottom: `0px`
- rect: x `951`, y `769`, width `311`, height `48`, bottom `817`
- in viewport: `true`
- media row still present: `true`
- network response: deliberate HTTP `409`

Long-row containment remained fixed:

- media list clientWidth/scrollWidth: `277/277`
- row clientWidth/scrollWidth: `273/273`
- row right `1238` vs list right `1250`
- filename strong clientWidth/scrollWidth: `190/427`, `text-overflow: ellipsis`
- audio clientWidth/scrollWidth: `257/257`, display `block`
- row and audio inside their containers: `true`

Controls remained clickable:

- native audio click started playback: `paused=false`, `currentTime=0.032`, `readyState=4`
- Delete click triggered the protected deletion request

Only the deliberate409 network response/browser resource error appeared; no unexpected console errors.

## Artifacts

- `media_sticky_error_final.json`
- `media_sticky_error_final.log`
- `24_sticky_error_immediate.png`
