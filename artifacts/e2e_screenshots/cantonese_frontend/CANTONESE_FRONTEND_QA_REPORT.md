# Cantonese frontend QA report

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome, fixture backend (`OPENACE_CI_SYNTH_FIXTURE=1`), rebuilt frontend.

## Result

All requested Cantonese checks passed. No implementation defect was found in this focused run.

Harness transparency: the first two automation attempts stopped on test-script issues (wrong full-width `＋ New` selector, then an incorrect one-track assumption because new projects already include `Lead Vocal`). The corrected run used visible UI creation/editing and completed; these were not application defects.

## UI creation/editing verification

A fresh project was created through the visible New control. A second vocal track was added and selected through the track panel. Language was changed to **Cantonese** in the visible Voice panel.

Four notes were drawn with the pencil tool and edited through the visible double-click lyric editor:

| start | duration | pitch | lyric |
|---:|---:|---:|---|
| 0 | 480 | 60 | 我 |
| 480 | 480 | 62 | 愛 |
| 960 | 480 | 64 | 你 |
| 1440 | 480 | 65 | 唔 |

The notes and Chinese lyrics remain visible in the piano roll.

## Backend phoneme verification

Exact generated phoneme sequences:

- `我` → `ŋ ɔː`
- `愛` → `ɔː i`
- `你` → `n ɛː i`
- `唔` → `m̩`

Checks passed:

- no `la` or placeholder tokens
- every first vowel starts at 0ms
- syllabic `m̩` is generated for `唔`
- manual phoneme editor opens pre-populated with exact real tokens `ŋ ɔː` for `我`
- Breath & Phoneme lane visibly shows real Cantonese token blocks rather than placeholders

## SoulX metadata contract

Supplemental implementation-path validation against the real `external/SoulX-Singer/.../phone_set.json` passed. Built target metadata had:

- canonical language `Cantonese`
- exact syllable phones `yue_ngo5 yue_oi3 yue_nei5 yue_m4`
- text sequence `我 愛 你 唔 <SP>`

This was a direct implementation-path check because the CI fixture vocal engine validates orchestration rather than invoking the external neural model.

## Fixture render

The visible **Render vocal** control was clicked.

- POST `/render/vocal`: HTTP 200
- job id: `job_3bd4bb5c0a83`
- status: `completed`
- progress: `1.0`
- engine: `explicit CI synthesis fixture`
- error: none
- output: `/home/ubuntu/repos/OpenACE/data/renders/project_bb0cb3a14f04/job_3bd4bb5c0a83/vocal.wav`

No Cantonese/Jyutping/phoneset validation error occurred.

## Invalid lyric negative test

The first note lyric was changed to non-CJK `abc` through the visible lyric editor.

The UI surfaced a clear save error:

```text
save failed: 422: {"detail":"Cantonese lyrics contain unsupported character 'a'"}
```

Backend persistence remained unchanged as `我 愛 你 唔`, proving there was no silent substitution. The deliberate negative test produced the expected HTTP 422 and a browser resource-load console message for that rejected request. During the valid creation/edit/render phase, there were zero console errors and zero unexpected network failures.

## Evidence

- `01_cantonese_language_selected.png`
- `02_notes_created_empty.png`
- `03_cantonese_notes_lyrics.png`
- `04_phoneme_editor.png`
- `04_phoneme_lane.png`
- `04_phoneme_lane_crop2x.png`
- `05_fixture_render_job.png`
- `06_invalid_lyric_error.png`
- `06_invalid_error_banner_crop2x.png`
- `evidence_cantonese_montage.png`
- `cantonese_results.json`
