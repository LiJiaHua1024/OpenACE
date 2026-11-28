# Zero-shot reference trimming QA

Real visible Chrome, exact `1272x837`; frontend rebuilt/cache-busted (`index-Byy7OoYP.js`); backend restarted. Project `project_c70a9950c171`. No repo code modified.

## Verdict

Passed end to end; no implementation defects confirmed.

## Exact evidence

- Uploaded 5.0s nonzero mono 48kHz reference.
- Default trim controls exactly `0` and `5`.
- Set visible numeric controls to `1.0–2.5` and clicked **Trim copy**.
- New copy auto-selected/assigned:
  - id `voice_0200ef542985`
  - duration exactly `1.5s`
  - backend file exactly `72000` frames at `48000Hz`, mono
  - metadata `source_voice_id=voice_1aa12f9071ec`, trim range `1.0–2.5`
  - quality reanalyzed: peak `0.35001`, RMS `-12.13dBFS`, voiced `1.5s`
  - correct warning: `reference is shorter than 2s; zero-shot timbre may be unstable`
- Native audition `duration=1.5`, progressed to `0.672997s`, correct `/api/voices/.../audio` URL.
- Original preserved in list with original `5.0s` duration and unchanged path.
- Reload persistence exact; trimmed copy remained selected/assigned and both voices remained listed.
- Invalid direct API ranges returned exact readable details and no growth:
  - end<=start: `trim requires 0 <= start < end`
  - tiny range: `trimmed reference voice is too short`
  - beyond duration: `trim end exceeds reference duration`
- UI beyond-duration path showed polished `trim end exceeds reference duration`, count unchanged.
- End<=start/tiny are additionally prevented by disabled Trim copy button in normal UI.
- Rename trimmed copy to `Trimmed QA Copy` passed.
- Deleting trimmed copy removed only it; original remained; project assignment cleared exactly.
- Layout contained/no horizontal overflow.
- Console/network clean except one expected422 resource entry for intentional invalid UI trim.

## Files

`voice_trim_results.json`, fixture `trim_source.wav`, screenshots `01`-`05` in this directory.
