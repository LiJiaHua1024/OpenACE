# Per-Track Stem Export QA

## Scope

Visible Chrome validation of the new `STEMS` export button on `Stem Export QA`, a two-track project using distinct real rendered fixture WAVs. The frontend was rebuilt/cache-busted and the backend restarted before testing. Downloaded zips/WAVs were inspected with Python/soundfile. Supplemental API/CLI/MCP checks were run for signal-chain coverage. Repo code was not modified.

## Test setup

- Lead Vocal: real fixture WAV `job_e3fd88274832/vocal.wav`; clip start `0`, duration `960`, offset `0`, volume `0.8`, gain `0 dB`.
- Harmony Vocal: independently different real fixture WAV `job_05ff23623dab/vocal.wav`; clip start `480`, duration `960`, slipped offset `240`, volume `0.5`, gain `-6 dB`, fade in/out `120` ticks.
- The two source stems were effectively uncorrelated (`cross-correlation ≈ 0.00155`), making mute/solo contamination easy to detect.

## Assertions

- **STEMS button visible and downloads a zip:** passed. Browser download suggested `Stem Export QA_stems.zip`, size `271,543` bytes.
- **Zip shape/manifest:** passed. Baseline zip contained exactly `stems_manifest.json`, `01_Lead_Vocal.wav`, and `02_Harmony_Vocal.wav`.
- **Per-track separation/no fake audio:** passed. Both stems were non-silent 48 kHz stereo PCM WAVs:
  - Lead peak `0.318213`, RMS `0.173544`, duration `1.0 s`
  - Harmony peak `0.099678`, RMS `0.039710`, duration `1.5 s`
  - Lead/harmony normalized cross-correlation `0.00155`.
- **No per-stem loudness normalization; volume/gain/fades/slip/timeline exact:** passed. Independent reconstruction of the expected signal chain matched sample-for-sample within PCM24 tolerance:
  - Lead max absolute difference `1.04e-7`
  - Harmony max absolute difference `1.19e-7`
  - Harmony includes the expected 0.5 s leading timeline silence, slipped 0.25 s source offset, `0.5 × 10^(-6/20)` gain scaling, and edge fades.
- **Mute semantics in stems:** passed. With Harmony muted, zip contained only `01_Lead_Vocal.wav` plus manifest.
- **Solo semantics in stems:** passed. With Harmony soloed, zip contained only `01_Harmony_Vocal.wav` plus manifest.
- **Master WAV regression downloads:** passed. Browser download suggested `Stem Export QA.wav`; baseline master was 48 kHz stereo, 1.5 s, non-silent.
- **Mute/solo semantics fixed in master export:** passed. Despite master loudness scaling, waveform-shape correlations were exact:
  - Harmony-muted master vs Lead stem `0.99999999999995`; vs Harmony stem `0.00155`
  - Harmony-solo master vs Harmony stem `0.99999999999937`; vs Lead stem `0.00155`
- **Automatic same-track crossfade supplemental signal-chain check:** passed. An overlapping audible/silent clip pair matched the expected cosine outgoing envelope with max difference `2.33e-7`; RMS fell from `0.28261` before overlap to `0.19983` at the overlap center and `0.03214` near the overlap end, then silence after the outgoing clip.
- **Tempo-aware slip/timeline supplemental check:** passed. With a tempo change from 120 to 60 BPM at tick 960, a clip at tick 1440 with offset 240/duration 480 exported audio starting at exactly ~2.0 s and matched the expected 0.5–1.5 s source slice with max difference `2.20e-13`.
- **CLI format regression:** passed. `openace-tool export project_ed0ec15342eb stems ...` exited 0 and produced a valid zip with manifest/two stems.
- **MCP format regression:** passed. Real stdio MCP `export_project(fmt="stems")` returned bytes `271543` and produced a valid zip with manifest/two stems.
- **Layout:** passed. Export grid buttons were visible in a 3-column layout; right panel `clientWidth == scrollWidth == 311`, body width `1600 == innerWidth`.
- **Console/page/network:** passed. No console errors, page errors, or HTTP >=400 responses during the browser run.

## Minor issue found

- **Export working directories are not cleaned up.** Each stems export leaves an uncompressed sibling directory next to the zip (for example `data/exports/Stem Export QA_stems/`, and local `cli_stems/` / `mcp_stems/` beside CLI/MCP zips). The zip contents themselves were correct; this is disk/noise hygiene rather than an audio correctness failure.

## Caveats

- Master loudness normalization prevents direct absolute sample comparison with unnormalized stems, so master inclusion/exclusion was verified by normalized waveform-shape correlation.
- Perceptual audio quality was not evaluated; this was deterministic digital signal-chain validation.
- Supplemental crossfade/tempo checks used API-exported zips rather than additional browser clicks; they are labeled as signal-chain evidence rather than recorded UI coverage.

## Artifacts

- `baseline_stems.zip`, `mute_harmony_stems.zip`, `solo_harmony_stems.zip`
- `baseline_master.wav`, `mute_harmony_master.wav`, `solo_harmony_master.wav`
- `cli_stems.zip`, `mcp_stems.zip`
- `crossfade_envelope_stems.zip`, `tempo_offset_stems.zip`
- `browser_export_results.json`, `stem_audio_analysis.json`, `supplemental_signalchain_results.json`
- extracted manifests and screenshots/waveform plot in this directory
