# Agent Project Operations QA Report

Focused acceptance in real visible Chrome with fixture backend. Viewport 1272x837 where feasible.

## Results

| Check | Result | Evidence |
|---|---:|---|
| CLI create-project appears in open selector without reload | PASS | `01_cli_create_selector_live.png` |
| CLI duplicate-project appears in open selector without reload | PASS | `02_cli_duplicate_selector_live.png` |
| External delete updates selector/current workspace live | PASS | `03_external_delete_fallback.png` |
| No duplicate project entry after external delete | PASS | duplicate options count 0 |
| Local UI delete works exactly once | PASS | backend count 171 -> 170; one confirm dialog |
| import-audio CLI help available | PASS | exit 0 |
| Real audio import with available faster-whisper tiny model | PASS | CLI exit 0, project `project_29fcb07f9df4` appeared live |
| Imported audio project content visible | PASS | 4 notes, 3 nonempty lyrics (`Ooh,`/`ooh,`), English |
| Layout at 1272x837 | PASS | `06_imported_audio_project_open.png`; no overlap observed |
| Console/network health | PASS | no console errors; no network failures |

## Quantitative details

- External duplicate deletion: project count 172 -> 171.
- Local deletion: project count 171 -> 170.
- Untitled project count remained 25 before/after external deletion, so no duplicate fallback project was created.
- Backend deletion verification showed deleted IDs absent.
- Real import used cached `faster-whisper-tiny` model explicitly via `OPENACE_WHISPER_MODEL=tiny`; output had 4 notes and 3 nonempty transcribed lyrics.

## Caveats

- Real-model audio import was practical because faster-whisper and the tiny model cache were already available. This validates orchestration/import behavior on the supplied local vocal sample, not production ASR quality across models/languages.
- No implementation defects were confirmed in this focused run.
