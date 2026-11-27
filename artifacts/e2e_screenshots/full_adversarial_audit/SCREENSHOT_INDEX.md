# Full adversarial audit screenshot index

Project: `project_dd9a28d7eaa0`
Viewport: exact `1272×837` CSS pixels; screenshots are 2× device pixels.

| File | What it proves / visual review note |
|---|---|
| `00_initial_1272x837.png` | App opened cache-busted at exact target viewport. |
| `01_new_project_transport_fit.png` | New project and transport fit without body overflow/wrapping. |
| `02_notes_drawn.png` | Two notes visibly drawn during the primary scripted pass. The intended third note missed because the harness coordinate was invalid; see supplemental proof. |
| `03_lyrics_phonemes_cjk.png` | Chinese lyrics and regenerated phonemes visible on drawn notes. |
| `04_transpose_controls.png` | ±1/±12 semitone transpose controls visible; state verified in backend. |
| `05_automation_curves.png` | Pitch curve plus Air/Tension curve editing surface with nonzero point counts. |
| `06_zoom.png` | Zoom state after slider interaction (`112→136`). |
| `07_uploads.png` | Voice library after reference upload; selected reference voice card is readable and professional. Minor textarea text clipping is visible but not functional. |
| `08_vocal_render.png` | Vocal render and Vocal2BGM jobs completed; render entries visible. |
| `09_alt_drag_repaint_held.png` | Held Alt-drag repaint selection overlay visible (2,827 yellow pixels). |
| `10_alt_drag_repaint_numeric.png` | Numeric repaint range state (`0.32→1.09`). |
| `11_repaint_replacement_arrangement.png` | Repaint job completed and arrangement clip labeled `Repaint` replaced/updated. |
| `11b_svc_conversion.png` | SVC conversion job completed and SVC audio track/clip appeared in arrangement. |
| `12_playback.png` | Playback state after transport play; expected render sources loaded. |
| `13_export_panel.png` | Export panel with WAV/MP4/MID/LRC/USTX/SVP/VPR visible. Also exposes toolbar truncation at the center-right edge. |
| `toolbar_truncation_zoom.png` | Zoomed evidence that the editor toolbar overflows and the selection readout is truncated. |
| `14_exports_downloaded.png` | Final state after all seven visible export buttons were used. |
| `15_mcp_sse_live_update.png` | MCP-added note updated the open track card live through SSE (`2 notes→3 notes`). |
| `16_supplemental_drawn_note.png` | Supplemental real pencil draw in clear note space increased note count `3→4`, proving the earlier third-note miss was harness aiming. |
| `screenshot_index_contact_sheet.jpg` | Contact sheet of the ten primary screenshots used for visual roughness/discontinuity review. |

## Visual review summary

No blank panes, hard UI断层, missing arrangement waveforms, dead render/export controls, or console/network breakage were observed in the main flow. The clearest visual roughness is the piano editor toolbar: its content measures 764 px inside a 714 px container at exact 1272×837, so the selection count/hint is clipped. Secondary polish issue: helper text in the lyric-correction textarea is vertically tight/clipped, but the control remains usable.
