import { useEffect, useRef } from 'react'
import type { Project, TimelineState, Track } from '../types'

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
  trackId: string
  startX: number
  originalOffset: number
}

export default function ArrangementView(props: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const scrollTicks = props.timeline.scrollTicks
  const pxPerBeat = props.timeline.pxPerBeat
  const dragRef = useRef<DragState | null>(null)
  const repaintDragRef = useRef<{ anchorTicks: number; currentTicks: number } | null>(null)
  const ppq = props.project.ppq

  const xForTick = (ticks: number) => LABEL_WIDTH + ((ticks - scrollTicks) / ppq) * pxPerBeat
  const tickForX = (x: number) => Math.max(0, Math.round(scrollTicks + ((x - LABEL_WIDTH) / pxPerBeat) * ppq))

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const parent = canvas.parentElement!
    const draw = () => {
      const rect = parent.getBoundingClientRect()
      const dpr = window.devicePixelRatio || 1
      canvas.width = Math.floor(rect.width * dpr)
      canvas.height = Math.floor(rect.height * dpr)
      canvas.style.width = `${rect.width}px`
      canvas.style.height = `${rect.height}px`
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
          ctx.fillStyle = '#eafff8'; ctx.font = '9px Inter'; if (w > 40) ctx.fillText(clip.label || 'audio', x + 5, y + 21)
          // Minimal waveform-like occupancy stripes computed from clip identity, not audio pretense.
          ctx.strokeStyle = '#ffffff26'
          for (let wx = x + 5; wx < x + w - 5; wx += 7) {
            const amp = 3 + ((wx * 17) % 9)
            ctx.beginPath(); ctx.moveTo(wx, y + ROW_HEIGHT / 2 - amp); ctx.lineTo(wx, y + ROW_HEIGHT / 2 + amp); ctx.stroke()
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
  }, [props.project, props.selectedTrackId, props.playheadTicks, props.repaintRange, scrollTicks, pxPerBeat, ppq])

  function pointer(event: React.PointerEvent) {
    const rect = canvasRef.current!.getBoundingClientRect()
    return { x: event.clientX - rect.left, y: event.clientY - rect.top }
  }

  function trackAt(y: number) {
    const index = Math.floor((y - RULER_HEIGHT) / ROW_HEIGHT)
    return index >= 0 ? props.project.tracks[index] : undefined
  }

  function contentRange(track: Track) {
    let start = Infinity, end = -Infinity
    for (const note of track.notes) { start = Math.min(start, note.start_ticks); end = Math.max(end, note.start_ticks + note.duration_ticks) }
    for (const clip of track.clips) { start = Math.min(start, clip.start_ticks); end = Math.max(end, clip.start_ticks + (clip.duration_ticks || ppq * 8)) }
    return Number.isFinite(start) ? { start, end } : null
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
    const range = contentRange(track)
    if (!range) return
    const x1 = xForTick(range.start), x2 = xForTick(range.end)
    if (pos.x >= x1 && pos.x <= x2) {
      props.beginTransaction()
      dragRef.current = { trackId: track.id, startX: pos.x, originalOffset: 0 }
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
    if (!drag) return
    const deltaTicks = Math.round(((pos.x - drag.startX) / pxPerBeat) * ppq / (ppq / 4)) * (ppq / 4)
    if (deltaTicks === drag.originalOffset) return
    const change = deltaTicks - drag.originalOffset
    drag.originalOffset = deltaTicks
    props.updateProject(project => {
      const track = project.tracks.find(t => t.id === drag.trackId)
      if (!track) return
      const minimum = Math.min(0, ...track.notes.map(n => n.start_ticks), ...track.clips.map(c => c.start_ticks))
      const safeChange = Math.max(change, -minimum)
      for (const note of track.notes) note.start_ticks = Math.max(0, note.start_ticks + safeChange)
      for (const clip of track.clips) clip.start_ticks = Math.max(0, clip.start_ticks + safeChange)
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

  function onWheel(event: React.WheelEvent) {
    if (event.ctrlKey || event.metaKey) {
      props.onTimelineChange({ ...props.timeline, pxPerBeat: Math.max(32, Math.min(360, pxPerBeat * (event.deltaY > 0 ? .9 : 1.1))) })
    } else {
      props.onTimelineChange({ ...props.timeline, scrollTicks: Math.max(0, scrollTicks + event.deltaY * 2 + event.deltaX * 2) })
    }
  }

  return (
    <div className="arrangement-view">
      <canvas ref={canvasRef} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onWheel={onWheel} />
    </div>
  )
}
