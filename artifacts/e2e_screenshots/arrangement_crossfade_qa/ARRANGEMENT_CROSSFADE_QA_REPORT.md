# Arrangement automatic crossfade QA report

Date: 2026-04-27  
Branch: `devin/1795696369-dynamic-expression`  
Mode: visible Chrome at 1272×837, driven through Playwright/CDP against a backend restarted from the current working tree.

## Result

The requested adversarial crossfade loop completed. No blocking application defect was found.

One non-blocking usability concern: at the dense 34px arrangement row height, the `auto xfade` label shares the same cramped area as the clip label (`B high`). It remains distinguishable, but the text stack is visually crowded.

## Fixture/setup

- Project: `project_20951d120efc`.
- API setup was used only to create two accompaniment clips from deterministic band-separated fixture media:
  - `A low`: 220Hz-dominant clip, initially `0–960 ticks`.
  - `B high`: 523Hz-dominant clip, initially `960–1920 ticks`.
- The overlap itself was created through a real visible-UI drag.

## UI findings

- Initial clips were adjacent with no automatic crossfade shading.
- Dragging `B high` backward through the arrangement UI changed starts to `[0,720]`, creating a `720–960 tick` overlap.
- Cyan shading/curve appeared in the overlap only. Pixel histogram review found bright-cyan crossfade pixels spanning canvas x `231–288` after the drag and zero in the outside x `300–350` control region.
- Undo restored adjacent clips and removed the crossfade field; redo restored it.
- Trimming the first clip from `960` to `840 ticks` narrowed the cyan field to about x `231–263`; restoring the trim re-expanded it to x `231–288`.
- Zoomed visual review shows correct direction: outgoing curve descends left-to-right, incoming curve ascends left-to-right.
- No cyan overlap field appeared outside the clips.
- Dragging the first clip's top-right manual fade handle inside the overlap zone still worked; `fade_out_ticks=240` persisted while overlap positions remained `[0,720]`.

## Playback

Instrumented WebAudio playback captured 26 `linearRampToValueAtTime` calls. Values clearly formed the expected complementary shapes:

```text
0.8000 → 0.7932 → 0.7727 → … → 0.1044 → 0.0001
0.1044 → 0.2071 → 0.3061 → … → 0.7932 → 0.8000
```

The transport advanced during playback and no dead control or deadlock was observed.

## Export measurement

The visible WAV export control was clicked, and the exported master was additionally fetched deterministically for analysis.

Measured overlap window: `0.75–1.0s`.

| Metric | Result | Interpretation |
|---|---:|---|
| Overlap/outside broadband RMS | `0.997×` | consistent with equal-power crossfade; simple uncorrelated summing would be about `1.414×` |
| Low/outgoing envelope correlation with cosine | `0.99988` | correct outgoing direction |
| High/incoming envelope correlation with sine | `0.99962` | correct incoming direction |

Measured normalized band profiles:

```text
low/outgoing:  0.983 → 0.916 → 0.798 → 0.606 → 0.398 → 0.146
high/incoming: 0.124 → 0.402 → 0.606 → 0.789 → 0.920 → 0.987
```

The profiles closely match equal-power cosine/sine envelopes.

## Console/network health

No browser console errors or network failures were captured.

## Harness transparency note

The first canvas pixel-count predicate was too broad and counted bright clip-edge/text pixels. The visual assertions were therefore rechecked using post-hoc screenshot pixel histograms plus zoomed manual review. Corrected analysis is stored in `crossfade_results.json`; this was a measurement-method issue, not an application failure.

## Important artifacts

- `evidence_crossfade_visual_states.png` — zoomed before/overlap/undo/trim/restore/manual-fade montage.
- `evidence_crossfade_export_analysis.png` — measured cosine/sine band envelopes and overlap RMS comparison.
- `crossfade_master.wav` — exported master used for measurement.
- `03_overlap_crossfade_visual.png` — full crossfade UI screenshot.
- `08_playback_crossfade.png` — playback state.
- `10_manual_fade_composes.png` — manual fade composed with overlap.
- `crossfade_results.json` — machine-readable assertions.
