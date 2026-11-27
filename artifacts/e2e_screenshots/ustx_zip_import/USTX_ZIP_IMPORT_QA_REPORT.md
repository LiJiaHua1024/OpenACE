# USTX zip import QA report

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, fixture backend, rebuilt frontend.

## Result

All requested USTX zip-import checks passed.

## Fixture

Created `ustx_zip_fixture.zip` containing exactly two root entries:

- `song.ustx`
- `media.wav`

The USTX has internal project name `Zip Wave Import QA` and one wave part:

- name/label `Hook`
- relative path `media.wav`
- position `480`
- file duration `1000ms`
- skip `240`
- trim `240`
- fade-in `48`
- fade-out `96`

## Verification

- Visible `Import USTX` control accept attribute is `.ustx,.zip`.
- Real browser file chooser path was used.
- `/api/import/ustx` returned HTTP 200.
- Imported project opened with UI/backend title `Zip Wave Import QA`.
- Arrangement remained healthy and visibly showed the green `Hook` audio clip.
- Backend project contains exactly one audio track and one clip.
- Clip timing restored exactly:
  - `start_ticks=480`
  - `offset_ticks=240`
  - `duration_ticks=480`
  - `fade_in_ticks=48`
  - `fade_out_ticks=96`
- Bundled media was extracted persistently and exists at:
  - `/home/ubuntu/repos/OpenACE/data/uploads/ustx_packages/pkg_6izxapm_/media.wav`
  - size `288044` bytes
- No console errors or network failures occurred.

## Evidence

- `01_before_zip_import.png`
- `02_after_zip_import.png`
- `ustx_zip_fixture.zip`
- `zip_fixture.ustx`
- `ustx_zip_results.json`
