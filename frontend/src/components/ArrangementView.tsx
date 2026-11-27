import { useEffect, useRef, useState } from 'react'
import { renderFileUrl } from '../api'
import { crossfadeGainAt, crossfadeIntervals } from '../crossfade'
import type { AudioClip, Project, TimelineState, Track } from '../types'

const LABEL_WIDTH = 64
const RULER_HEIGHT = 24
const ROW_HEIGHT = 34

interface Props {
  project: Project
  selectedTrackId?: string
  playheadTicks: number
  onSelect(trackId: string): void
  onSeek(ticks: number): void
  beginTransaction(): void
  endTransaction(): void
  updateProject(mutator: (project: Project) => void, transient?: boolean): void
  timeline: TimelineState
  onTimelineChange(timeline: TimelineState): void
  repaintRange: { start: number; end: number }
  onRepaintRange(range: { start: number; end: number }): void
}

interface DragState {
  kind: 'clip' | 'notes' | 'trim-left' | 'trim-right' | 'fade-in' | 'fade-out'
  trackId: string
  startX: number
  clipId?: string
  originalStart: number
  originalDuration?: number
  originalOffset?: number
  originalFade?: number
  noteOriginals?: Record<string, number>
}

interface WaveformData {
  peaks: Float32Array
  durationSeconds: number
}

export default function ArrangementView(props: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const scrollTicks = props.timeline.scrollTicks
  const pxPerBeat = props.timeline.pxPerBeat
  const dragRef = useRef<DragState | null>(null)
  const repaintDragRef = useRef<{ anchorTicks: number; currentTicks: number } | null>(null)
  const [waveforms, setWaveforms] = useState<Record<string, WaveformData>>({})
  const [menu, setMenu] = useState<{ x: number; y: number; trackId: string; clipId: string | null; ticks: number } | null>(null)
  const clipClipboardRef = useRef<AudioClip | null>(null)
  const [, setClipClipboardVersion] = useState(0)
  const waveformCache = useRef(new Map<string, Promise<WaveformData>>())
  const audioContextRef = useRef<AudioContext | null>(null)
  const ppq = props.project.ppq

  const xForTick = (ticks: number) => LABEL_WIDTH + ((ticks - scrollTicks) / ppq) * pxPerBeat
  const tickForX = (x: number) => Math.max(0, Math.round(scrollTicks + ((x - LABEL_WIDTH) / pxPerBeat) * ppq))

  useEffect(() => {
    let cancelled = false
    const paths = Array.from(new Set(props.project.tracks.flatMap(track => track.clips.map(clip => clip.path))))
    for (const path of paths) {
      if (!path || waveforms[path]) continue
      if (!waveformCache.current.has(path)) {
        waveformCache.current.set(path, (async () => {
          const url = renderFileUrl(path)
          if (!url) throw new Error('no render URL')
          const response = await fetch(url)
          if (!response.ok) throw new Error(`waveform fetch failed: ${response.status}`)
          audioContextRef.current ||= new AudioContext()
          const buffer = await audioContextRef.current.decodeAudioData(await response.arrayBuffer())
          const bins = 1024
          const peaks = new Float32Array(bins)
          for (let channel = 0; channel < buffer.numberOfChannels; channel++) {
            const data = buffer.getChannelData(channel)
            for (let bin = 0; bin < bins; bin++) {
              const start = Math.floor((bin / bins) * data.length)
              const end = Math.max(start + 1, Math.floor(((bin + 1) / bins) * data.length))
              let peak = 0
              for (let i = start; i < end; i += Math.max(1, Math.floor((end - start) / 24))) {
                peak = Math.max(peak, Math.abs(data[i]))
              }
              peaks[bin] = Math.max(peaks[bin], peak)
            }
          }
          return { peaks, durationSeconds: buffer.duration }
        })())
      }
      waveformCache.current.get(path)!
        .then(peaks => {
          if (!cancelled) setWaveforms(current => current[path] ? current : { ...current, [path]: peaks })
        })
        .catch(() => {})
    }
    return () => { cancelled = true }
  }, [props.project, waveforms])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const parent = canvas.parentElement!
    const draw = () => {
      const rect = parent.getBoundingClientRect()
      const dpr = window.devicePixelRatio || 1
      const pixelWidth = Math.max(1, Math.floor(rect.width * dpr))
      const pixelHeight = Math.max(1, Math.floor(rect.height * dpr))
      if (canvas.width !== pixelWidth) canvas.width = pixelWidth
      if (canvas.height !== pixelHeight) canvas.height = pixelHeight
      if (canvas.style.width !== `${rect.width}px`) canvas.style.width = `${rect.width}px`
      if (canvas.style.height !== `${rect.height}px`) canvas.style.height = `${rect.height}px`
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.save(); ctx.scale(dpr, dpr)
      const width = rect.width
      const height = rect.height
      ctx.fillStyle = '#0f121c'; ctx.fillRect(0, 0, width, height)
      const barTicks = ppq * props.project.time_signature.numerator
      const endTicks = scrollTicks + ((width - LABEL_WIDTH) / pxPerBeat) * ppq + barTicks
      for (let t = Math.floor(scrollTicks / (ppq / 4)) * (ppq / 4); t < endTicks; t += ppq / 4) {
        const x = xForTick(t)
        ctx.strokeStyle = t % barTicks === 0 ? '#48516e' : t % ppq === 0 ? '#2c3349' : '#202638'
        ctx.beginPath(); ctx.moveTo(x, RULER_HEIGHT); ctx.lineTo(x, height); ctx.stroke()
        if (t % barTicks === 0) {
          ctx.fillStyle = '#9aa5c5'; ctx.font = '10px Inter'; ctx.fillText(String(Math.floor(t / barTicks) + 1), x + 4, 16)
        }
      }
      ctx.fillStyle = '#151927'; ctx.fillRect(0, 0, width, RULER_HEIGHT)
      ctx.fillStyle = '#151927'; ctx.fillRect(0, 0, LABEL_WIDTH, height)
      ctx.strokeStyle = '#333b54'; ctx.beginPath(); ctx.moveTo(0, RULER_HEIGHT - .5); ctx.lineTo(width, RULER_HEIGHT - .5); ctx.stroke()
      ctx.beginPath(); ctx.moveTo(LABEL_WIDTH - .5, 0); ctx.lineTo(LABEL_WIDTH - .5, height); ctx.stroke()

      props.project.tracks.forEach((track, index) => {
        const y = RULER_HEIGHT + index * ROW_HEIGHT
        ctx.fillStyle = index % 2 ? '#121622' : '#141827'
        ctx.fillRect(0, y, width, ROW_HEIGHT)
        ctx.strokeStyle = '#262d42'; ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke()
        if (track.id === props.selectedTrackId) {
          ctx.fillStyle = '#7568ff18'; ctx.fillRect(0, y, width, ROW_HEIGHT)
        }
        ctx.fillStyle = track.color; ctx.fillRect(0, y + 5, 4, ROW_HEIGHT - 10)

        if (track.type === 'vocal' && track.notes.length) {
          const groups: { start: number; end: number; count: number }[] = []
          const sorted = [...track.notes].sort((a, b) => a.start_ticks - b.start_ticks)
          for (const note of sorted) {
            const last = groups[groups.length - 1]
            if (last && note.start_ticks - last.end <= ppq * 2) {
              last.end = note.start_ticks + note.duration_ticks; last.count++
            } else groups.push({ start: note.start_ticks, end: note.start_ticks + note.duration_ticks, count: 1 })
          }
          for (const group of groups) {
            const x = xForTick(group.start)
            const w = Math.max(10, ((group.end - group.start) / ppq) * pxPerBeat)
            const grad = ctx.createLinearGradient(x, y, x, y + ROW_HEIGHT)
            grad.addColorStop(0, track.color); grad.addColorStop(1, '#302a68')
            ctx.fillStyle = grad
            ctx.beginPath(); ctx.roundRect(x, y + 7, w, ROW_HEIGHT - 14, 4); ctx.fill()
            ctx.fillStyle = '#ffffffcc'; ctx.font = '9px Inter'; if (w > 32) ctx.fillText(`${group.count} notes`, x + 5, y + 21)
          }
        }
        for (const clip of track.clips) {
          const duration = clip.duration_ticks || ppq * 8
          const x = xForTick(clip.start_ticks)
          const w = Math.max(14, (duration / ppq) * pxPerBeat)
          ctx.fillStyle = '#25b995aa'
          ctx.beginPath(); ctx.roundRect(x, y + 6, w, ROW_HEIGHT - 12, 4); ctx.fill()
          ctx.strokeStyle = '#55e7c5'; ctx.stroke()
          ctx.fillStyle = '#eafff86e'
          ctx.fillRect(x + 1, y + 8, 2, ROW_HEIGHT - 16)
          ctx.fillRect(x + w - 3, y + 8, 2, ROW_HEIGHT - 16)
          ctx.fillStyle = '#eafff8'; ctx.font = '9px Inter'; if (w > 40) ctx.fillText(clip.label || 'audio', x + 5, y + 21)
          const waveform = waveforms[clip.path]
          if (waveform) {
            ctx.strokeStyle = '#eafff866'
            ctx.lineWidth = 1
            const center = y + ROW_HEIGHT / 2 + 2
            const usable = Math.max(1, w - 10)
            const secondsPerTick = 60 / (props.project.bpm * ppq)
            const sourceOffset = (clip.offset_ticks || 0) * secondsPerTick
            const visibleDuration = duration * secondsPerTick
            const startRatio = Math.max(0, Math.min(1, sourceOffset / Math.max(0.001, waveform.durationSeconds)))
            const endRatio = Math.max(startRatio, Math.min(1, (sourceOffset + visibleDuration) / Math.max(0.001, waveform.durationSeconds)))
            for (let px = 0; px < usable; px++) {
              const ratio = startRatio + (px / usable) * (endRatio - startRatio)
              const index = Math.min(waveform.peaks.length - 1, Math.floor(ratio * waveform.peaks.length))
              const clipTickPosition = (px / usable) * duration
              const fadeIn = Math.max(0, clip.fade_in_ticks || 0)
              const fadeOut = Math.max(0, clip.fade_out_ticks || 0)
              const manualFadeGain = Math.min(
                fadeIn ? Math.max(0, Math.min(1, clipTickPosition / fadeIn)) : 1,
                fadeOut ? Math.max(0, Math.min(1, (duration - clipTickPosition) / fadeOut)) : 1,
              )
              const fadeGain = manualFadeGain * crossfadeGainAt(track, clip, clip.start_ticks + clipTickPosition)
              const amp = Math.max(0.35, waveform.peaks[index] * (ROW_HEIGHT - 15) * 0.48 * fadeGain)
              const wx = x + 5 + px
              ctx.beginPath(); ctx.moveTo(wx, center - amp); ctx.lineTo(wx, center + amp); ctx.stroke()
            }
          } else if (w > 74) {
            ctx.fillStyle = '#b9fff088'; ctx.font = '8px Inter'; ctx.fillText('analyzing waveform…', x + 6, y + ROW_HEIGHT - 9)
          }
          const fadeInWidth = Math.min(w / 2, ((clip.fade_in_ticks || 0) / ppq) * pxPerBeat)
          const fadeOutWidth = Math.min(w / 2, ((clip.fade_out_ticks || 0) / ppq) * pxPerBeat)
          ctx.strokeStyle = '#ffffffb8'
          ctx.lineWidth = 1
          if (fadeInWidth > 1) {
            ctx.beginPath(); ctx.moveTo(x + 1, y + ROW_HEIGHT - 7); ctx.lineTo(x + fadeInWidth, y + 7); ctx.stroke()
          }
          if (fadeOutWidth > 1) {
            ctx.beginPath(); ctx.moveTo(x + w - fadeOutWidth, y + 7); ctx.lineTo(x + w - 1, y + ROW_HEIGHT - 7); ctx.stroke()
          }
          ctx.fillStyle = '#ffffffd8'
          ctx.fillRect(x + Math.max(1, fadeInWidth) - 2, y + 5, 4, 6)
          ctx.fillRect(x + w - Math.max(1, fadeOutWidth) - 2, y + 5, 4, 6)
          for (const interval of crossfadeIntervals(track, clip)) {
            const sx = xForTick(interval.startTicks)
            const ex = xForTick(interval.endTicks)
            if (ex < x || sx > x + w) continue
            ctx.fillStyle = '#58d8ff20'
            ctx.fillRect(sx, y + 6, ex - sx, ROW_HEIGHT - 12)
            ctx.strokeStyle = '#74e4ffcc'
            ctx.lineWidth = 1.2
            ctx.beginPath()
            for (let step = 0; step <= 12; step++) {
              const position = interval.startTicks + (interval.endTicks - interval.startTicks) * step / 12
              const gx = xForTick(position)
              const gain = crossfadeGainAt(track, clip, position)
              const gy = y + ROW_HEIGHT - 7 - gain * (ROW_HEIGHT - 14)
              if (step === 0) ctx.moveTo(gx, gy)
              else ctx.lineTo(gx, gy)
            }
            ctx.stroke()
            if (interval.role === 'incoming' && ex - sx > 34) {
              ctx.fillStyle = '#bdf2ff'
              ctx.font = '7px Inter'
              ctx.fillText('XF', sx + 3, y + 11)
            }
          }
        }
      })
      if (props.repaintRange.end > props.repaintRange.start) {
        const startTicks = props.repaintRange.start * props.project.bpm * ppq / 60
        const endTicks = props.repaintRange.end * props.project.bpm * ppq / 60
        const sx = xForTick(startTicks)
        const ex = xForTick(endTicks)
        if (ex >= LABEL_WIDTH && sx < width) {
          ctx.fillStyle = '#f4b94224'
          ctx.fillRect(sx, RULER_HEIGHT, ex - sx, height - RULER_HEIGHT)
          ctx.strokeStyle = '#f4b942'
          ctx.lineWidth = 1.5
          ctx.strokeRect(sx, RULER_HEIGHT, ex - sx, height - RULER_HEIGHT)
          ctx.fillStyle = '#ffd27a'
          ctx.font = '10px Inter'
          ctx.fillText('repaint region', Math.max(LABEL_WIDTH + 5, sx + 5), RULER_HEIGHT + 13)
        }
      }

      const px = xForTick(props.playheadTicks)
      if (px >= LABEL_WIDTH && px < width) {
        ctx.strokeStyle = '#ff4f78'; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, height); ctx.stroke()
      }
      ctx.restore()
    }
    draw()
    const observer = new ResizeObserver(draw)
    observer.observe(parent)
    return () => observer.disconnect()
  }, [props.project, props.selectedTrackId, props.playheadTicks, props.repaintRange, waveforms, scrollTicks, pxPerBeat, ppq])

  function pointer(event: React.PointerEvent) {
    const rect = canvasRef.current!.getBoundingClientRect()
    return { x: event.clientX - rect.left, y: event.clientY - rect.top }
  }

  function trackAt(y: number) {
    const index = Math.floor((y - RULER_HEIGHT) / ROW_HEIGHT)
    return index >= 0 ? props.project.tracks[index] : undefined
  }

  function noteGroups(track: Track) {
    const groups: { start: number; end: number; noteIds: string[] }[] = []
    const sorted = [...track.notes].sort((a, b) => a.start_ticks - b.start_ticks)
    for (const note of sorted) {
      const end = note.start_ticks + note.duration_ticks
      const last = groups[groups.length - 1]
      if (last && note.start_ticks - last.end <= ppq * 2) {
        last.end = end
        last.noteIds.push(note.id)
      } else {
        groups.push({ start: note.start_ticks, end, noteIds: [note.id] })
      }
    }
    return groups
  }

  function clipDuration(clip: any) {
    return clip.duration_ticks || ppq * 8
  }

  function clipAt(track: Track, x: number) {
    return track.clips.find(clip => {
      const duration = clipDuration(clip)
      const x1 = xForTick(clip.start_ticks)
      const x2 = x1 + Math.max(14, (duration / ppq) * pxPerBeat)
      return x >= x1 && x <= x2
    })
  }

  function clipFadeAt(track: Track, x: number, y: number) {
    const trackIndex = props.project.tracks.findIndex(item => item.id === track.id)
    const rowY = RULER_HEIGHT + trackIndex * ROW_HEIGHT
    if (y < rowY + 6 || y > rowY + 14) return null
    for (const clip of track.clips) {
      const duration = clipDuration(clip)
      const x1 = xForTick(clip.start_ticks)
      const width = Math.max(14, (duration / ppq) * pxPerBeat)
      const x2 = x1 + width
      const fadeInEnd = x1 + Math.min(width / 2, ((clip.fade_in_ticks || 0) / ppq) * pxPerBeat)
      const fadeOutStart = x2 - Math.min(width / 2, ((clip.fade_out_ticks || 0) / ppq) * pxPerBeat)
      if ((clip.fade_in_ticks || 0) > 0 && Math.abs(x - fadeInEnd) <= 8) return { clip, edge: 'in' as const }
      if ((clip.fade_out_ticks || 0) > 0 && Math.abs(x - fadeOutStart) <= 8) return { clip, edge: 'out' as const }
      if (Math.abs(x - x1) <= 8) return { clip, edge: 'in' as const }
      if (Math.abs(x - x2) <= 8) return { clip, edge: 'out' as const }
    }
    return null
  }

  function clipEdgeAt(track: Track, x: number) {
    for (const clip of track.clips) {
      const duration = clipDuration(clip)
      const x1 = xForTick(clip.start_ticks)
      const x2 = x1 + Math.max(14, (duration / ppq) * pxPerBeat)
      if (Math.abs(x - x1) <= 6) return { clip, edge: 'left' as const }
      if (Math.abs(x - x2) <= 6) return { clip, edge: 'right' as const }
    }
    return null
  }

  function noteGroupAt(track: Track, x: number) {
    return noteGroups(track).find(group => {
      const x1 = xForTick(group.start)
      const x2 = xForTick(group.end)
      return x >= x1 && x <= x2
    })
  }

  function onPointerDown(event: React.PointerEvent) {
    const pos = pointer(event)
    if (event.altKey && pos.x >= LABEL_WIDTH) {
      const ticks = tickForX(pos.x)
      repaintDragRef.current = { anchorTicks: ticks, currentTicks: ticks }
      props.onRepaintRange({
        start: ticks * 60 / (props.project.bpm * ppq),
        end: ticks * 60 / (props.project.bpm * ppq) + 0.001,
      })
      canvasRef.current?.setPointerCapture(event.pointerId)
      return
    }
    if (pos.y < RULER_HEIGHT) { props.onSeek(tickForX(pos.x)); return }
    const track = trackAt(pos.y)
    if (!track) return
    props.onSelect(track.id)
    if (pos.x < LABEL_WIDTH) return
    const fadeHit = clipFadeAt(track, pos.x, pos.y)
    if (fadeHit) {
      props.beginTransaction()
      dragRef.current = {
        kind: fadeHit.edge === 'in' ? 'fade-in' : 'fade-out',
        trackId: track.id,
        startX: pos.x,
        clipId: fadeHit.clip.id,
        originalStart: fadeHit.clip.start_ticks,
        originalDuration: clipDuration(fadeHit.clip),
        originalFade: fadeHit.edge === 'in' ? (fadeHit.clip.fade_in_ticks || 0) : (fadeHit.clip.fade_out_ticks || 0),
      }
      canvasRef.current?.setPointerCapture(event.pointerId)
      return
    }
    const edgeHit = clipEdgeAt(track, pos.x)
    if (edgeHit) {
      props.beginTransaction()
      dragRef.current = {
        kind: edgeHit.edge === 'left' ? 'trim-left' : 'trim-right',
        trackId: track.id,
        startX: pos.x,
        clipId: edgeHit.clip.id,
        originalStart: edgeHit.clip.start_ticks,
        originalDuration: clipDuration(edgeHit.clip),
        originalOffset: edgeHit.clip.offset_ticks || 0,
      }
      canvasRef.current?.setPointerCapture(event.pointerId)
      return
    }
    const clip = clipAt(track, pos.x)
    if (clip) {
      props.beginTransaction()
      dragRef.current = { kind: 'clip', trackId: track.id, startX: pos.x, clipId: clip.id, originalStart: clip.start_ticks }
      canvasRef.current?.setPointerCapture(event.pointerId)
      return
    }
    const group = noteGroupAt(track, pos.x)
    if (group) {
      props.beginTransaction()
      const noteOriginals: Record<string, number> = {}
      for (const note of track.notes) if (group.noteIds.includes(note.id)) noteOriginals[note.id] = note.start_ticks
      dragRef.current = { kind: 'notes', trackId: track.id, startX: pos.x, originalStart: group.start, noteOriginals }
      canvasRef.current?.setPointerCapture(event.pointerId)
    }
  }

  function onPointerMove(event: React.PointerEvent) {
    const pos = pointer(event)
    const repaintDrag = repaintDragRef.current
    if (repaintDrag) {
      repaintDrag.currentTicks = tickForX(pos.x)
      const startTicks = Math.min(repaintDrag.anchorTicks, repaintDrag.currentTicks)
      const endTicks = Math.max(repaintDrag.anchorTicks, repaintDrag.currentTicks)
      props.onRepaintRange({
        start: startTicks * 60 / (props.project.bpm * ppq),
        end: endTicks * 60 / (props.project.bpm * ppq),
      })
      return
    }
    const drag = dragRef.current
    if (!drag) {
      const hoverTrack = trackAt(pos.y)
      const edge = hoverTrack && pos.x >= LABEL_WIDTH ? clipEdgeAt(hoverTrack, pos.x) : null
      const hoverClip = hoverTrack && pos.x >= LABEL_WIDTH ? clipAt(hoverTrack, pos.x) : null
      if (canvasRef.current) canvasRef.current.style.cursor = edge ? 'ew-resize' : hoverClip ? 'grab' : 'default'
      return
    }
    const deltaTicks = Math.round(((pos.x - drag.startX) / pxPerBeat) * ppq / (ppq / 4)) * (ppq / 4)
    props.updateProject(project => {
      const track = project.tracks.find(t => t.id === drag.trackId)
      if (!track) return
      if (drag.kind === 'clip') {
        const clip = track.clips.find(item => item.id === drag.clipId)
        if (clip) clip.start_ticks = Math.max(0, drag.originalStart + deltaTicks)
      } else if (drag.kind === 'fade-in' || drag.kind === 'fade-out') {
        const clip = track.clips.find(item => item.id === drag.clipId)
        if (!clip || drag.originalDuration === undefined || drag.originalFade === undefined) return
        const maxFade = Math.max(0, Math.floor(drag.originalDuration / 2))
        const signedDelta = drag.kind === 'fade-in' ? deltaTicks : -deltaTicks
        const fade = Math.max(0, Math.min(maxFade, drag.originalFade + signedDelta))
        if (drag.kind === 'fade-in') clip.fade_in_ticks = fade
        else clip.fade_out_ticks = fade
      } else if (drag.kind === 'trim-left' || drag.kind === 'trim-right') {
        const clip = track.clips.find(item => item.id === drag.clipId)
        if (!clip || drag.originalDuration === undefined || drag.originalOffset === undefined) return
        const minimum = ppq / 4
        if (drag.kind === 'trim-left') {
          const maxDelta = drag.originalDuration - minimum
          const minDelta = -Math.min(drag.originalStart, drag.originalOffset)
          const appliedDelta = Math.max(minDelta, Math.min(maxDelta, deltaTicks))
          clip.start_ticks = drag.originalStart + appliedDelta
          clip.offset_ticks = Math.max(0, drag.originalOffset + appliedDelta)
          clip.duration_ticks = drag.originalDuration - appliedDelta
        } else {
          const waveform = waveforms[clip.path]
          const sourceEndTicks = waveform ? Math.round(waveform.durationSeconds * project.bpm * ppq / 60) : Infinity
          const maxDuration = Math.max(minimum, sourceEndTicks - drag.originalOffset)
          clip.duration_ticks = Math.max(minimum, Math.min(maxDuration, drag.originalDuration + deltaTicks))
        }
      } else if (drag.noteOriginals) {
        const minStart = Math.min(...Object.values(drag.noteOriginals))
        const allowedDelta = Math.max(deltaTicks, -minStart)
        for (const note of track.notes) {
          const original = drag.noteOriginals[note.id]
          if (original !== undefined) note.start_ticks = original + allowedDelta
        }
      }
    }, true)
  }

  function onPointerUp(event: React.PointerEvent) {
    repaintDragRef.current = null
    if (dragRef.current) {
      dragRef.current = null
      props.endTransaction()
    }
    canvasRef.current?.releasePointerCapture(event.pointerId)
  }


  function cloneClip(clip: AudioClip): AudioClip {
    return JSON.parse(JSON.stringify(clip))
  }

  function copyClip(menuItem: { trackId: string; clipId: string | null }) {
    const track = props.project.tracks.find(item => item.id === menuItem.trackId)
    const clip = track?.clips.find(item => item.id === menuItem.clipId)
    if (!clip) return
    clipClipboardRef.current = cloneClip(clip)
    setClipClipboardVersion(version => version + 1)
    setMenu(null)
  }

  function pasteClip(menuItem: { trackId: string; ticks: number }) {
    const clipboard = clipClipboardRef.current
    if (!clipboard) return
    const start = Math.max(0, Math.round(menuItem.ticks / (ppq / 4)) * (ppq / 4))
    props.updateProject(project => {
      const track = project.tracks.find(item => item.id === menuItem.trackId)
      if (!track) return
      track.clips.push({
        ...cloneClip(clipboard),
        id: `clip_${crypto.randomUUID().slice(0, 12)}`,
        start_ticks: start,
      })
      track.clips.sort((a, b) => a.start_ticks - b.start_ticks)
    }, false)
    setMenu(null)
  }

  function duplicateClip(menuItem: { trackId: string; clipId: string | null }) {
    props.updateProject(project => {
      const track = project.tracks.find(item => item.id === menuItem.trackId)
      if (!track) return
      const index = track.clips.findIndex(item => item.id === menuItem.clipId)
      if (index < 0) return
      const clip = track.clips[index]
      const duration = clipDuration(clip)
      track.clips.splice(index + 1, 0, {
        ...cloneClip(clip),
        id: `clip_${crypto.randomUUID().slice(0, 12)}`,
        start_ticks: clip.start_ticks + duration,
      })
    }, false)
    setMenu(null)
  }

  function deleteClip(menuItem: { trackId: string; clipId: string | null }) {
    props.updateProject(project => {
      const track = project.tracks.find(item => item.id === menuItem.trackId)
      if (!track) return
      track.clips = track.clips.filter(item => item.id !== menuItem.clipId)
    }, false)
    setMenu(null)
  }

  function splitClip(menuItem: { trackId: string; clipId: string | null; ticks: number }) {
    props.updateProject(project => {
      const track = project.tracks.find(item => item.id === menuItem.trackId)
      if (!track) return
      const index = track.clips.findIndex(item => item.id === menuItem.clipId)
      if (index < 0) return
      const clip = track.clips[index]
      const splitTicks = Math.round(menuItem.ticks / (ppq / 4)) * (ppq / 4)
      const duration = clipDuration(clip)
      const end = clip.start_ticks + duration
      if (splitTicks <= clip.start_ticks + ppq / 8 || splitTicks >= end - ppq / 8) return
      const firstDuration = splitTicks - clip.start_ticks
      const second = {
        ...clip,
        id: `clip_${crypto.randomUUID().slice(0, 12)}`,
        start_ticks: splitTicks,
        duration_ticks: end - splitTicks,
        offset_ticks: (clip.offset_ticks || 0) + firstDuration,
        fade_in_ticks: 0,
      }
      clip.duration_ticks = firstDuration
      clip.fade_out_ticks = 0
      track.clips.splice(index + 1, 0, second)
    }, false)
    setMenu(null)
  }


  function updateClipGain(menuItem: { trackId: string; clipId: string }, gainDb: number) {
    props.updateProject(project => {
      const track = project.tracks.find(item => item.id === menuItem.trackId)
      const clip = track?.clips.find(item => item.id === menuItem.clipId)
      if (clip) clip.gain_db = Math.max(-24, Math.min(12, gainDb))
    }, false)
  }

  function onContextMenu(event: React.MouseEvent) {
    event.preventDefault()
    const rect = canvasRef.current!.getBoundingClientRect()
    const pos = { x: event.clientX - rect.left, y: event.clientY - rect.top }
    const track = trackAt(pos.y)
    if (!track || pos.x < LABEL_WIDTH) return
    const clip = clipAt(track, pos.x)
    setMenu({ x: pos.x, y: pos.y, trackId: track.id, clipId: clip?.id || null, ticks: tickForX(pos.x) })
  }

  function onWheel(event: React.WheelEvent) {
    if (event.ctrlKey || event.metaKey) {
      props.onTimelineChange({ ...props.timeline, pxPerBeat: Math.max(32, Math.min(360, pxPerBeat * (event.deltaY > 0 ? .9 : 1.1))) })
    } else {
      props.onTimelineChange({ ...props.timeline, scrollTicks: Math.max(0, scrollTicks + event.deltaY * 2 + event.deltaX * 2) })
    }
  }

  const menuWidth = 204
  const menuHeight = menu?.clipId ? 130 : 40
  const menuMargin = menu?.clipId ? 1 : 4
  const menuLeft = menu ? Math.max(4, Math.min(menu.x, (canvasRef.current?.clientWidth || 640) - menuWidth - 4)) : 0
  const menuTop = menu ? Math.max(menuMargin, Math.min(menu.y, 132 - menuHeight - menuMargin)) : 0

  return (
    <div className="arrangement-view" onClick={() => setMenu(null)}>
      <canvas ref={canvasRef} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onWheel={onWheel} onContextMenu={onContextMenu} />
      {menu && (
        <div className="piano-context-menu arrangement-context-menu" style={{ left: menuLeft, top: menuTop }} onClick={event => event.stopPropagation()}>
          {menu.clipId && <button onClick={() => splitClip(menu)}>Split at cursor</button>}
          {menu.clipId && <button onClick={() => copyClip(menu)}>Copy</button>}
          <button disabled={!clipClipboardRef.current} onClick={() => pasteClip(menu)}>Paste at cursor</button>
          {menu.clipId && <button onClick={() => duplicateClip(menu)}>Duplicate</button>}
          {menu.clipId && <button onClick={() => deleteClip(menu)}>Delete</button>}
          {menu.clipId && (() => {
            const track = props.project.tracks.find(item => item.id === menu.trackId)
            const clip = track?.clips.find(item => item.id === menu.clipId)
            if (!clip) return null
            return (
              <label className="clip-gain-control">Clip gain
                <span>
                  <input
                    key={`${clip.id}:${clip.gain_db || 0}`}
                    type="number"
                    min="-24"
                    max="12"
                    step="0.5"
                    defaultValue={clip.gain_db || 0}
                    onChange={event => {
                      const raw = event.target.value
                      if (raw === '' || raw === '-' || raw === '.' || raw === '-.') return
                      updateClipGain(menu, Number(raw))
                    }}
                  />
                  dB
                </span>
              </label>
            )
          })()}
        </div>
      )}
    </div>
  )
}
