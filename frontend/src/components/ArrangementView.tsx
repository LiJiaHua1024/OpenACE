import { useEffect, useRef, useState } from 'react'
import { api, renderFileUrl } from '../api'
import { crossfadeGainAt, crossfadeIntervals } from '../crossfade'
import type { AudioClip, Project, TimelineState, Track } from '../types'
import { barTicks as musicalBarTicks, secondsBetweenTicks, secondsToTicks, secondsToTicksFrom, tickDurationSeconds, ticksToSeconds } from '../tempo'

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
  loopRange?: { start: number; end: number } | null
  loopEnabled?: boolean
  onLoopRange(range: { start: number; end: number } | null): void
}

interface DragState {
  kind: 'clip' | 'notes' | 'trim-left' | 'trim-right' | 'fade-in' | 'fade-out' | 'slip'
  trackId: string
  startX: number
  startY: number
  clipId?: string
  originalStart: number
  originalDuration?: number
  originalOffset?: number
  originalFade?: number
  noteOriginals?: Record<string, number>
  clipOriginals?: { trackId: string; trackIndex: number; clipId: string; startTicks: number }[]
  clipAssignments?: Record<string, string>
}

interface WaveformData {
  peaks: Float32Array
  durationSeconds: number
}

export default function ArrangementView(props: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const arrangementRef = useRef<HTMLDivElement | null>(null)
  const [arrangementScrollTop, setArrangementScrollTop] = useState(0)
  const scrollTicks = props.timeline.scrollTicks
  const pxPerBeat = props.timeline.pxPerBeat
  const dragRef = useRef<DragState | null>(null)
  const repaintDragRef = useRef<{ anchorTicks: number; currentTicks: number } | null>(null)
  const loopDragRef = useRef<{ anchorTicks: number; startX: number; moved: boolean } | null>(null)
  const [waveforms, setWaveforms] = useState<Record<string, WaveformData>>({})
  const [menu, setMenu] = useState<{ x: number; y: number; trackId: string; clipId: string | null; ticks: number } | null>(null)
  const [selectedClips, setSelectedClips] = useState<{ trackId: string; clipId: string }[]>([])
  const [marquee, setMarquee] = useState<{ startX: number; startY: number; currentX: number; currentY: number; additive: boolean } | null>(null)
  const [mediaDropTarget, setMediaDropTarget] = useState<{ x: number; y: number; height: number } | null>(null)
  const mediaDropLeaveTimer = useRef<number | null>(null)
  const clipClipboardRef = useRef<{ trackId: string; clip: AudioClip; relativeStart: number }[]>([])
  const [, setClipClipboardVersion] = useState(0)
  const waveformCache = useRef(new Map<string, Promise<WaveformData>>())
  const audioContextRef = useRef<AudioContext | null>(null)
  const ppq = props.project.ppq
  const snapGrid = Math.max(1, Math.round(ppq / Math.max(1, props.timeline.gridDivision ?? 4)))

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
      const barTicks = musicalBarTicks(props.project)
      const endTicks = scrollTicks + ((width - LABEL_WIDTH) / pxPerBeat) * ppq + barTicks
      for (let t = Math.floor(scrollTicks / snapGrid) * snapGrid; t < endTicks; t += snapGrid) {
        const x = xForTick(t)
        ctx.strokeStyle = t % barTicks === 0 ? '#48516e' : t % ppq === 0 ? '#2c3349' : '#202638'
        ctx.beginPath(); ctx.moveTo(x, RULER_HEIGHT); ctx.lineTo(x, height); ctx.stroke()
        if (t % barTicks === 0) {
          ctx.fillStyle = '#9aa5c5'; ctx.font = '10px Inter'; ctx.fillText(String(Math.floor(t / barTicks) + 1), x + 4, arrangementScrollTop + 16)
        }
      }
      ctx.fillStyle = '#151927'; ctx.fillRect(0, arrangementScrollTop, width, RULER_HEIGHT)
      ctx.fillStyle = '#151927'; ctx.fillRect(0, 0, LABEL_WIDTH, height)
      ctx.strokeStyle = '#333b54'; ctx.beginPath(); ctx.moveTo(0, arrangementScrollTop + RULER_HEIGHT - .5); ctx.lineTo(width, arrangementScrollTop + RULER_HEIGHT - .5); ctx.stroke()
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
        ctx.fillStyle = '#dbe3f6d9'; ctx.font = '9px Inter'
        ctx.fillText(track.name, 8, y + 20, 50)

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
          const clipSelected = selectedClips.some(item => item.trackId === track.id && item.clipId === clip.id)
          ctx.strokeStyle = clipSelected ? '#ffffff' : '#55e7c5'
          ctx.lineWidth = clipSelected ? 2 : 1
          ctx.stroke()
          ctx.lineWidth = 1
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
            const sourceOffset = secondsBetweenTicks(props.project, clip.start_ticks - (clip.offset_ticks || 0), clip.start_ticks)
            const visibleDuration = tickDurationSeconds(props.project, clip.start_ticks, duration)
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
          const transcribedLyrics = clip.transcribed_lyrics || []
          if (transcribedLyrics.length) {
            const lyricSourceOffset = secondsBetweenTicks(props.project, clip.start_ticks - (clip.offset_ticks || 0), clip.start_ticks)
            const lyricVisibleDuration = tickDurationSeconds(props.project, clip.start_ticks, duration)
            const lyricVisibleEnd = lyricSourceOffset + lyricVisibleDuration
            ctx.font = '8px Inter'
            let lastLyricX = -Infinity
            for (const word of transcribedLyrics) {
              if (word.end < lyricSourceOffset || word.start > lyricVisibleEnd) continue
              const localStart = Math.max(0, word.start - lyricSourceOffset)
              const tickPosition = clip.start_ticks + secondsToTicksFrom(props.project, clip.start_ticks, localStart)
              const lyricX = xForTick(tickPosition)
              if (lyricX < x - 1 || lyricX > x + w - 4) continue
              const drawX = Math.max(lyricX, x + 4)
              if (drawX - lastLyricX < 18) continue
              ctx.fillStyle = '#fff0a8e6'
              ctx.fillText(word.text, drawX, y + ROW_HEIGHT - 7, Math.max(18, x + w - drawX - 5))
              lastLyricX = drawX
            }
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
      if (marquee) {
        const x1 = Math.min(marquee.startX, marquee.currentX)
        const x2 = Math.max(marquee.startX, marquee.currentX)
        const y1 = Math.min(marquee.startY, marquee.currentY)
        const y2 = Math.max(marquee.startY, marquee.currentY)
        ctx.fillStyle = '#7c8cff18'
        ctx.fillRect(x1, y1, x2 - x1, y2 - y1)
        ctx.strokeStyle = '#aab6ffcc'
        ctx.setLineDash([4, 3])
        ctx.strokeRect(x1 + .5, y1 + .5, x2 - x1, y2 - y1)
        ctx.setLineDash([])
      }
      ctx.fillStyle = '#151927'
      ctx.fillRect(0, arrangementScrollTop, width, RULER_HEIGHT)
      ctx.strokeStyle = '#333b54'
      ctx.beginPath(); ctx.moveTo(0, arrangementScrollTop + RULER_HEIGHT - .5); ctx.lineTo(width, arrangementScrollTop + RULER_HEIGHT - .5); ctx.stroke()
      ctx.fillStyle = '#9aa5c5'
      ctx.font = '10px Inter'
      for (let t = Math.floor(scrollTicks / barTicks) * barTicks; t < endTicks; t += barTicks) {
        ctx.fillText(String(Math.floor(t / barTicks) + 1), xForTick(t) + 4, arrangementScrollTop + 16)
      }
      if (props.loopRange && props.loopRange.end > props.loopRange.start) {
        const sx = xForTick(props.loopRange.start)
        const ex = xForTick(props.loopRange.end)
        if (ex >= LABEL_WIDTH && sx < width) {
          ctx.fillStyle = props.loopEnabled ? '#55c7ff24' : '#55c7ff10'
          ctx.fillRect(sx, RULER_HEIGHT, ex - sx, height - RULER_HEIGHT)
          ctx.strokeStyle = props.loopEnabled ? '#61d5ff' : '#61d5ff66'
          ctx.lineWidth = 1.5
          ctx.strokeRect(sx, RULER_HEIGHT, ex - sx, height - RULER_HEIGHT)
          ctx.fillStyle = '#a8eaff'
          ctx.font = '10px Inter'
          ctx.fillText(props.loopEnabled ? 'loop' : 'loop off', Math.max(LABEL_WIDTH + 5, sx + 5), RULER_HEIGHT + 26)
        }
      }
      if (props.repaintRange.end > props.repaintRange.start) {
        const startTicks = secondsToTicks(props.project, props.repaintRange.start)
        const endTicks = secondsToTicks(props.project, props.repaintRange.end)
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
  }, [props.project, props.selectedTrackId, props.playheadTicks, props.repaintRange, props.loopRange, props.loopEnabled, waveforms, selectedClips, marquee, arrangementScrollTop, scrollTicks, pxPerBeat, ppq, snapGrid])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const handleNativeWheel = (event: WheelEvent) => {
      if (event.ctrlKey || event.metaKey) {
        event.preventDefault()
        props.onTimelineChange({ ...props.timeline, pxPerBeat: Math.max(32, Math.min(360, pxPerBeat * (event.deltaY > 0 ? .9 : 1.1))) })
      } else if (event.shiftKey) {
        event.preventDefault()
        props.onTimelineChange({ ...props.timeline, scrollTicks: Math.max(0, scrollTicks + event.deltaY * 2 + event.deltaX * 2) })
      } else if (event.deltaX) {
        event.preventDefault()
        props.onTimelineChange({ ...props.timeline, scrollTicks: Math.max(0, scrollTicks + event.deltaX * 2) })
      }
    }
    canvas.addEventListener('wheel', handleNativeWheel, { passive: false })
    return () => canvas.removeEventListener('wheel', handleNativeWheel)
  }, [props.timeline, props.onTimelineChange, scrollTicks, pxPerBeat])

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

  function selectionHas(trackId: string, clipId: string) {
    return selectedClips.some(item => item.trackId === trackId && item.clipId === clipId)
  }

  function clipSelectionItems(selection = selectedClips) {
    return selection.flatMap(item => {
      const track = props.project.tracks.find(trackItem => trackItem.id === item.trackId)
      const clip = track?.clips.find(clipItem => clipItem.id === item.clipId)
      return track && clip ? [{ trackId: item.trackId, clipId: item.clipId, clip }] : []
    })
  }

  function onPointerDown(event: React.PointerEvent) {
    const pos = pointer(event)
    if (event.altKey && pos.x >= LABEL_WIDTH) {
      const ticks = tickForX(pos.x)
      repaintDragRef.current = { anchorTicks: ticks, currentTicks: ticks }
      props.onRepaintRange({
        start: ticksToSeconds(props.project, ticks),
        end: ticksToSeconds(props.project, ticks) + 0.001,
      })
      canvasRef.current?.setPointerCapture(event.pointerId)
      return
    }
    if (pos.y >= arrangementScrollTop && pos.y < arrangementScrollTop + RULER_HEIGHT && pos.x >= LABEL_WIDTH) {
      loopDragRef.current = { anchorTicks: tickForX(pos.x), startX: pos.x, moved: false }
      canvasRef.current?.setPointerCapture(event.pointerId)
      return
    }
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
        startY: pos.y,
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
        startY: pos.y,
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
      const additive = event.ctrlKey || event.metaKey
      if (additive) {
        setSelectedClips(current => selectionHas(track.id, clip.id)
          ? current.filter(item => !(item.trackId === track.id && item.clipId === clip.id))
          : [...current, { trackId: track.id, clipId: clip.id }])
        return
      }
      const nextSelection = selectionHas(track.id, clip.id) && selectedClips.length > 1
        ? selectedClips
        : [{ trackId: track.id, clipId: clip.id }]
      setSelectedClips(nextSelection)
      const clipOriginals = clipSelectionItems(nextSelection).map(item => ({
        trackId: item.trackId,
        trackIndex: props.project.tracks.findIndex(trackItem => trackItem.id === item.trackId),
        clipId: item.clipId,
        startTicks: item.clip.start_ticks,
      }))
      props.beginTransaction()
      dragRef.current = {
        kind: event.shiftKey && nextSelection.length === 1 ? 'slip' : 'clip',
        trackId: track.id,
        startX: pos.x,
        startY: pos.y,
        clipId: clip.id,
        originalStart: clip.start_ticks,
        originalDuration: clipDuration(clip),
        originalOffset: clip.offset_ticks || 0,
        clipOriginals,
        clipAssignments: Object.fromEntries(clipOriginals.map(item => [item.clipId, item.trackId])),
      }
      canvasRef.current?.setPointerCapture(event.pointerId)
      return
    }
    const group = noteGroupAt(track, pos.x)
    if (group) {
      props.beginTransaction()
      const noteOriginals: Record<string, number> = {}
      for (const note of track.notes) if (group.noteIds.includes(note.id)) noteOriginals[note.id] = note.start_ticks
      dragRef.current = { kind: 'notes', trackId: track.id, startX: pos.x, startY: pos.y, originalStart: group.start, noteOriginals }
      canvasRef.current?.setPointerCapture(event.pointerId)
      return
    }
    const additive = event.ctrlKey || event.metaKey
    if (!additive) setSelectedClips([])
    setMarquee({ startX: pos.x, startY: pos.y, currentX: pos.x, currentY: pos.y, additive })
    canvasRef.current?.setPointerCapture(event.pointerId)
  }

  function onPointerMove(event: React.PointerEvent) {
    const pos = pointer(event)
    const loopDrag = loopDragRef.current
    if (loopDrag) {
      if (Math.abs(pos.x - loopDrag.startX) > 4) {
        loopDrag.moved = true
        const snap = (ticks: number) => Math.max(0, Math.round(ticks / snapGrid) * snapGrid)
        const currentTicks = snap(tickForX(pos.x))
        const anchorTicks = snap(loopDrag.anchorTicks)
        const start = Math.min(anchorTicks, currentTicks)
        const end = Math.max(anchorTicks, currentTicks)
        if (end - start >= snapGrid) props.onLoopRange({ start, end })
      }
      return
    }
    if (marquee) {
      setMarquee(current => current ? { ...current, currentX: pos.x, currentY: pos.y } : current)
      return
    }
    const repaintDrag = repaintDragRef.current
    if (repaintDrag) {
      repaintDrag.currentTicks = tickForX(pos.x)
      const startTicks = Math.min(repaintDrag.anchorTicks, repaintDrag.currentTicks)
      const endTicks = Math.max(repaintDrag.anchorTicks, repaintDrag.currentTicks)
      props.onRepaintRange({
        start: ticksToSeconds(props.project, startTicks),
        end: ticksToSeconds(props.project, endTicks),
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
    const deltaTicks = Math.round(((pos.x - drag.startX) / pxPerBeat) * ppq / snapGrid) * snapGrid
    props.updateProject(project => {
      if (drag.kind === 'clip' && drag.clipOriginals?.length) {
        const minStart = Math.min(...drag.clipOriginals.map(item => item.startTicks))
        const allowedDelta = Math.max(deltaTicks, -minStart)
        const rawTrackDelta = (pos.y - drag.startY) / ROW_HEIGHT
        const requestedTrackDelta = rawTrackDelta >= 0 ? Math.floor(rawTrackDelta + 0.5) : Math.ceil(rawTrackDelta - 0.5)
        const compatibleIndexes = project.tracks
          .map((trackItem, index) => ({ trackItem, index }))
          .filter(item => item.trackItem.type === 'audio' || item.trackItem.type === 'accompaniment')
          .map(item => item.index)
        const laneIndexes = compatibleIndexes.length ? compatibleIndexes : project.tracks.map((_, index) => index)
        const lanePositions = drag.clipOriginals.map(item => laneIndexes.indexOf(item.trackIndex))
        const movablePositions = lanePositions.filter(position => position >= 0)
        const minLanePosition = movablePositions.length ? Math.min(...movablePositions) : 0
        const maxLanePosition = movablePositions.length ? Math.max(...movablePositions) : 0
        const trackDelta = movablePositions.length
          ? Math.max(-minLanePosition, Math.min(laneIndexes.length - 1 - maxLanePosition, requestedTrackDelta))
          : 0
        for (const original of drag.clipOriginals) {
          const currentTrackId = drag.clipAssignments?.[original.clipId] || original.trackId
          const sourceTrack = project.tracks.find(item => item.id === currentTrackId)
          const clipIndex = sourceTrack?.clips.findIndex(item => item.id === original.clipId) ?? -1
          if (!sourceTrack || clipIndex < 0) continue
          const originalLanePosition = laneIndexes.indexOf(original.trackIndex)
          const targetTrack = originalLanePosition >= 0
            ? project.tracks[laneIndexes[originalLanePosition + trackDelta]]
            : sourceTrack
          if (!targetTrack) continue
          const [clip] = sourceTrack.clips.splice(clipIndex, 1)
          clip.start_ticks = original.startTicks + allowedDelta
          targetTrack.clips.push(clip)
          targetTrack.clips.sort((a, b) => a.start_ticks - b.start_ticks)
          if (drag.clipAssignments) drag.clipAssignments[clip.id] = targetTrack.id
        }
        return
      }
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
      } else if (drag.kind === 'slip') {
        const clip = track.clips.find(item => item.id === drag.clipId)
        if (!clip || drag.originalDuration === undefined || drag.originalOffset === undefined) return
        const waveform = waveforms[clip.path]
        const sourceEndTicks = waveform ? Math.round(secondsToTicksFrom(props.project, drag.originalStart - drag.originalOffset, waveform.durationSeconds)) : Infinity
        const maxOffset = Math.max(0, sourceEndTicks - drag.originalDuration)
        clip.offset_ticks = Math.max(0, Math.min(maxOffset, drag.originalOffset + deltaTicks))
      } else if (drag.kind === 'trim-left' || drag.kind === 'trim-right') {
        const clip = track.clips.find(item => item.id === drag.clipId)
        if (!clip || drag.originalDuration === undefined || drag.originalOffset === undefined) return
        const minimum = snapGrid
        if (drag.kind === 'trim-left') {
          const maxDelta = drag.originalDuration - minimum
          const minDelta = -Math.min(drag.originalStart, drag.originalOffset)
          const appliedDelta = Math.max(minDelta, Math.min(maxDelta, deltaTicks))
          clip.start_ticks = drag.originalStart + appliedDelta
          clip.offset_ticks = Math.max(0, drag.originalOffset + appliedDelta)
          clip.duration_ticks = drag.originalDuration - appliedDelta
        } else {
          const waveform = waveforms[clip.path]
          const sourceEndTicks = waveform ? Math.round(secondsToTicksFrom(props.project, clip.start_ticks - (clip.offset_ticks || 0), waveform.durationSeconds)) : Infinity
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
    const loopDrag = loopDragRef.current
    if (loopDrag) {
      if (!loopDrag.moved) props.onSeek(loopDrag.anchorTicks)
      loopDragRef.current = null
      canvasRef.current?.releasePointerCapture(event.pointerId)
      return
    }
    if (marquee) {
      const x1 = Math.min(marquee.startX, marquee.currentX)
      const x2 = Math.max(marquee.startX, marquee.currentX)
      const y1 = Math.min(marquee.startY, marquee.currentY)
      const y2 = Math.max(marquee.startY, marquee.currentY)
      if (x2 - x1 > 4 && y2 - y1 > 4) {
        const hits: { trackId: string; clipId: string }[] = []
        props.project.tracks.forEach((track, trackIndex) => {
          const rowTop = RULER_HEIGHT + trackIndex * ROW_HEIGHT + 6
          const rowBottom = rowTop + ROW_HEIGHT - 12
          if (rowBottom < y1 || rowTop > y2) return
          for (const clip of track.clips) {
            const duration = clipDuration(clip)
            const clipX1 = xForTick(clip.start_ticks)
            const clipX2 = clipX1 + Math.max(14, (duration / ppq) * pxPerBeat)
            if (clipX2 >= x1 && clipX1 <= x2) hits.push({ trackId: track.id, clipId: clip.id })
          }
        })
        setSelectedClips(current => marquee.additive ? Array.from(new Map([...current, ...hits].map(item => [`${item.trackId}:${item.clipId}`, item])).values()) : hits)
      }
      setMarquee(null)
    }
    repaintDragRef.current = null
    if (dragRef.current) {
      const assignments = dragRef.current.clipAssignments
      if (assignments) {
        setSelectedClips(current => current.map(item => assignments[item.clipId] ? { trackId: assignments[item.clipId], clipId: item.clipId } : item))
      }
      dragRef.current = null
      props.endTransaction()
    }
    canvasRef.current?.releasePointerCapture(event.pointerId)
  }


  function cloneClip(clip: AudioClip): AudioClip {
    return JSON.parse(JSON.stringify(clip))
  }

  function operationClips(menuItem: { trackId: string; clipId: string | null }) {
    const useSelection = menuItem.clipId && selectionHas(menuItem.trackId, menuItem.clipId) && selectedClips.length > 1
    if (useSelection) return clipSelectionItems()
    const track = props.project.tracks.find(item => item.id === menuItem.trackId)
    const clip = track?.clips.find(item => item.id === menuItem.clipId)
    return track && clip ? [{ trackId: track.id, clipId: clip.id, clip }] : []
  }

  function copyClip(menuItem: { trackId: string; clipId: string | null }) {
    const items = operationClips(menuItem)
    if (!items.length) return
    const minStart = Math.min(...items.map(item => item.clip.start_ticks))
    clipClipboardRef.current = items.map(item => ({
      trackId: item.trackId,
      clip: cloneClip(item.clip),
      relativeStart: item.clip.start_ticks - minStart,
    }))
    setClipClipboardVersion(version => version + 1)
    setMenu(null)
  }

  function pasteClip(menuItem: { trackId: string; ticks: number }) {
    const clipboard = clipClipboardRef.current
    if (!clipboard.length) return
    const groupStart = Math.max(0, Math.round(menuItem.ticks / snapGrid) * snapGrid)
    const nextSelection: { trackId: string; clipId: string }[] = []
    props.updateProject(project => {
      const fallbackTrack = project.tracks.find(item => item.id === menuItem.trackId)
      if (!fallbackTrack) return
      for (const item of clipboard) {
        const track = project.tracks.find(trackItem => trackItem.id === item.trackId) || fallbackTrack
        const id = `clip_${crypto.randomUUID().slice(0, 12)}`
        track.clips.push({
          ...cloneClip(item.clip),
          id,
          start_ticks: groupStart + item.relativeStart,
        })
        track.clips.sort((a, b) => a.start_ticks - b.start_ticks)
        nextSelection.push({ trackId: track.id, clipId: id })
      }
    }, false)
    setSelectedClips(nextSelection)
    setMenu(null)
  }

  function duplicateClip(menuItem: { trackId: string; clipId: string | null }) {
    const items = operationClips(menuItem)
    if (!items.length) return
    const minStart = Math.min(...items.map(item => item.clip.start_ticks))
    const groupEnd = Math.max(...items.map(item => item.clip.start_ticks + clipDuration(item.clip)))
    const shift = Math.max(snapGrid, groupEnd - minStart)
    const nextSelection: { trackId: string; clipId: string }[] = []
    props.updateProject(project => {
      for (const item of items) {
        const track = project.tracks.find(trackItem => trackItem.id === item.trackId)
        if (!track) continue
        const index = track.clips.findIndex(clipItem => clipItem.id === item.clipId)
        if (index < 0) continue
        const id = `clip_${crypto.randomUUID().slice(0, 12)}`
        track.clips.splice(index + 1, 0, {
          ...cloneClip(track.clips[index]),
          id,
          start_ticks: track.clips[index].start_ticks + shift,
        })
        track.clips.sort((a, b) => a.start_ticks - b.start_ticks)
        nextSelection.push({ trackId: track.id, clipId: id })
      }
    }, false)
    setSelectedClips(nextSelection)
    setMenu(null)
  }

  function deleteClip(menuItem: { trackId: string; clipId: string | null }) {
    const items = operationClips(menuItem)
    if (!items.length) return
    props.updateProject(project => {
      for (const item of items) {
        const track = project.tracks.find(trackItem => trackItem.id === item.trackId)
        if (track) track.clips = track.clips.filter(clipItem => clipItem.id !== item.clipId)
      }
    }, false)
    setSelectedClips([])
    setMenu(null)
  }

  function rippleDeleteClip(menuItem: { trackId: string; clipId: string | null }) {
    const items = operationClips(menuItem)
    if (!items.length) return
    props.updateProject(project => {
      const byTrack = new Map<string, typeof items>()
      for (const item of items) {
        byTrack.set(item.trackId, [...(byTrack.get(item.trackId) || []), item])
      }
      for (const [trackId, trackItems] of byTrack) {
        const track = project.tracks.find(item => item.id === trackId)
        if (!track) continue
        const ordered = [...trackItems].sort((a, b) => a.clip.start_ticks - b.clip.start_ticks)
        const intervals: { start: number; end: number }[] = []
        for (const item of ordered) {
          const startTick = item.clip.start_ticks
          const endTick = item.clip.start_ticks + clipDuration(item.clip)
          const last = intervals[intervals.length - 1]
          if (last && startTick <= last.end) last.end = Math.max(last.end, endTick)
          else intervals.push({ start: startTick, end: endTick })
        }
        const selectedIds = new Set(trackItems.map(item => item.clipId))
        track.clips = track.clips.filter(candidate => !selectedIds.has(candidate.id))
        for (const interval of [...intervals].reverse()) {
          const ripple = interval.end - interval.start
          for (const later of track.clips) {
            if (later.start_ticks >= interval.end) later.start_ticks = Math.max(0, later.start_ticks - ripple)
          }
        }
        track.clips.sort((a, b) => a.start_ticks - b.start_ticks)
      }
    }, false)
    setSelectedClips([])
    setMenu(null)
  }

  function splitClip(menuItem: { trackId: string; clipId: string | null; ticks: number }) {
    props.updateProject(project => {
      const track = project.tracks.find(item => item.id === menuItem.trackId)
      if (!track) return
      const index = track.clips.findIndex(item => item.id === menuItem.clipId)
      if (index < 0) return
      const clip = track.clips[index]
      const splitTicks = Math.round(menuItem.ticks / snapGrid) * snapGrid
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


  function rippleDeleteAcrossTracks(menuItem: { trackId: string; clipId: string | null }) {
    const items = operationClips(menuItem)
    if (!items.length) return
    const ordered = [...items].sort((a, b) => a.clip.start_ticks - b.clip.start_ticks)
    const intervals: { start: number; end: number }[] = []
    for (const item of ordered) {
      const start = item.clip.start_ticks
      const end = item.clip.start_ticks + clipDuration(item.clip)
      const last = intervals[intervals.length - 1]
      if (last && start <= last.end) last.end = Math.max(last.end, end)
      else intervals.push({ start, end })
    }
    const selectedIds = new Set(items.map(item => item.clipId))
    props.updateProject(project => {
      for (const track of project.tracks) {
        track.clips = track.clips.filter(candidate => !selectedIds.has(candidate.id))
      }
      for (const interval of [...intervals].reverse()) {
        const ripple = interval.end - interval.start
        for (const track of project.tracks) {
          for (const later of track.clips) {
            if (later.start_ticks >= interval.end) later.start_ticks = Math.max(0, later.start_ticks - ripple)
          }
          for (const note of track.notes) {
            if (note.start_ticks >= interval.end) note.start_ticks = Math.max(0, note.start_ticks - ripple)
          }
          for (const breath of track.breaths) {
            if (breath.start_ticks >= interval.end) breath.start_ticks = Math.max(0, breath.start_ticks - ripple)
          }
          for (const lane of Object.values(track.automation)) {
            for (const point of lane) {
              if (point.ticks >= interval.end) point.ticks = Math.max(0, point.ticks - ripple)
            }
            lane.sort((a, b) => a.ticks - b.ticks)
          }
          track.clips.sort((a, b) => a.start_ticks - b.start_ticks)
          track.notes.sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch)
        }
      }
    }, false)
    setSelectedClips([])
    setMenu(null)
  }


  async function rippleDeleteSelectedTimeRange() {
    const startTicks = secondsToTicks(props.project, props.repaintRange.start)
    const endTicks = secondsToTicks(props.project, props.repaintRange.end)
    if (endTicks <= startTicks) return
    props.beginTransaction()
    try {
      await api.rippleDeleteRange(props.project.id, startTicks, endTicks)
      const updated = await api.getProject(props.project.id)
      props.updateProject(project => {
        project.tracks = updated.tracks
        project.tempo_map = updated.tempo_map
      }, true)
    } catch {}
    props.endTransaction()
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
    if (clip && !selectionHas(track.id, clip.id)) setSelectedClips([{ trackId: track.id, clipId: clip.id }])
    setMenu({ x: pos.x, y: pos.y, trackId: track.id, clipId: clip?.id || null, ticks: tickForX(pos.x) })
  }

  function mediaDropPosition(event: React.DragEvent) {
    const rect = canvasRef.current!.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top
    const rawTicks = tickForX(x)
    const ticks = event.altKey ? rawTicks : Math.max(0, Math.round(rawTicks / ppq) * ppq)
    return { x, y, ticks, track: trackAt(y) }
  }

  function onMediaDragOver(event: React.DragEvent) {
    if (!event.dataTransfer.types.includes('application/x-openace-media')) return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
    const pos = mediaDropPosition(event)
    const row = Math.max(0, Math.floor((pos.y - RULER_HEIGHT) / ROW_HEIGHT))
    if (mediaDropLeaveTimer.current !== null) {
      window.clearTimeout(mediaDropLeaveTimer.current)
      mediaDropLeaveTimer.current = null
    }
    setMediaDropTarget({ x: xForTick(pos.ticks), y: RULER_HEIGHT + row * ROW_HEIGHT, height: ROW_HEIGHT })
  }

  function onMediaDragLeave(event: React.DragEvent) {
    const nextTarget = event.relatedTarget as Node | null
    if (nextTarget && (event.currentTarget as Node).contains(nextTarget)) return
    if (mediaDropLeaveTimer.current !== null) window.clearTimeout(mediaDropLeaveTimer.current)
    mediaDropLeaveTimer.current = window.setTimeout(() => {
      mediaDropLeaveTimer.current = null
      setMediaDropTarget(null)
    }, 160)
  }

  async function onMediaDrop(event: React.DragEvent) {
    const mediaName = event.dataTransfer.getData('application/x-openace-media')
    if (!mediaName) return
    event.preventDefault()
    const pos = mediaDropPosition(event)
    if (mediaDropLeaveTimer.current !== null) {
      window.clearTimeout(mediaDropLeaveTimer.current)
      mediaDropLeaveTimer.current = null
    }
    setMediaDropTarget(null)
    const targetTrack = pos.track && pos.track.type !== 'vocal' ? pos.track : undefined
    try {
      await api.placeMediaClip(props.project.id, mediaName, pos.ticks, targetTrack?.id)
    } catch {}
  }

  const arrangementContentHeight = Math.max(132, RULER_HEIGHT + props.project.tracks.length * ROW_HEIGHT + 6)
  const arrangementViewportHeight = Math.min(arrangementContentHeight, 210)
  const menuWidth = 204
  const menuHeight = menu?.clipId ? 156 : 74
  const menuMargin = menu?.clipId ? 1 : 4
  const menuLeft = menu ? Math.max(4, Math.min(menu.x, (canvasRef.current?.clientWidth || 640) - menuWidth - 4)) : 0
  const visibleMenuTop = arrangementScrollTop + menuMargin
  const visibleMenuBottom = arrangementScrollTop + arrangementViewportHeight - menuHeight - menuMargin
  const menuTop = menu ? Math.max(visibleMenuTop, Math.min(menu.y, Math.max(visibleMenuTop, visibleMenuBottom))) : 0

  return (
    <div ref={arrangementRef} className="arrangement-view" style={{ height: arrangementViewportHeight }} onClick={() => setMenu(null)} onScroll={event => setArrangementScrollTop((event.target as HTMLDivElement).scrollTop)}>
      <div className="arrangement-content" style={{ height: arrangementContentHeight }} onDragOver={onMediaDragOver} onDrop={event => { void onMediaDrop(event) }} onDragLeave={onMediaDragLeave}>
        <canvas ref={canvasRef} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onContextMenu={onContextMenu} />
        {mediaDropTarget && <div className="media-drop-indicator" style={{ left: mediaDropTarget.x, top: mediaDropTarget.y, height: mediaDropTarget.height }} />}
      {menu && (
        <div className="piano-context-menu arrangement-context-menu" style={{ left: menuLeft, top: menuTop }} onClick={event => event.stopPropagation()}>
          {menu.clipId && <button onClick={() => splitClip(menu)}>Split at cursor</button>}
          {menu.clipId && <button onClick={() => copyClip(menu)}>Copy</button>}
          <button disabled={!clipClipboardRef.current.length} onClick={() => pasteClip(menu)}>Paste at cursor</button>
          <button className="wide-menu-action" disabled={!(props.repaintRange.end > props.repaintRange.start)} onClick={() => { void rippleDeleteSelectedTimeRange() }}>Ripple delete time range</button>
          {menu.clipId && <button onClick={() => duplicateClip(menu)}>Duplicate</button>}
          {menu.clipId && <button onClick={() => deleteClip(menu)}>Delete</button>}
          {menu.clipId && <button onClick={() => rippleDeleteClip(menu)}>Ripple delete</button>}
          {menu.clipId && <button className="wide-menu-action" onClick={() => rippleDeleteAcrossTracks(menu)}>Ripple delete across tracks</button>}
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
    </div>
  )
}
