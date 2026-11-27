import { useEffect, useRef, useState } from 'react'
import { barTicks as musicalBarTicks, bpmAt, normalizedTempoMap } from '../tempo'
import type { Project, TimelineState } from '../types'

const HEIGHT = 54
const LABEL_WIDTH = 64
const MIN_BPM = 30
const MAX_BPM = 300

interface Props {
  project: Project
  timeline: TimelineState
  playheadTicks: number
  onTimelineChange(timeline: TimelineState): void
  beginTransaction(): void
  endTransaction(): void
  updateProject(mutator: (project: Project) => void, transient?: boolean): void
}

interface DragState {
  originalTick: number
  originalBpm: number
  startX: number
  startY: number
  anchor: boolean
}

function clampBpm(value: number) {
  return Math.max(MIN_BPM, Math.min(MAX_BPM, Math.round(value * 10) / 10))
}

function sortedPositivePoints(project: Project) {
  return (project.tempo_map || [])
    .filter(point => point.ticks > 0 && point.bpm > 0)
    .map(point => ({ ticks: Math.round(point.ticks), bpm: point.bpm }))
    .sort((a, b) => a.ticks - b.ticks)
}

function writePositivePoints(project: Project, points: { ticks: number; bpm: number }[]) {
  const deduped = new Map<number, number>()
  for (const point of points) {
    if (point.ticks > 0 && point.bpm > 0) deduped.set(Math.round(point.ticks), clampBpm(point.bpm))
  }
  project.tempo_map = Array.from(deduped, ([ticks, bpm]) => ({ ticks, bpm })).sort((a, b) => a.ticks - b.ticks)
}

export default function TempoLane(props: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const dragRef = useRef<DragState | null>(null)
  const [selectedTick, setSelectedTick] = useState<number | null>(null)
  const ppq = props.project.ppq
  const scrollTicks = props.timeline.scrollTicks
  const pxPerBeat = props.timeline.pxPerBeat
  const xForTick = (ticks: number) => LABEL_WIDTH + ((ticks - scrollTicks) / ppq) * pxPerBeat
  const tickForX = (x: number) => Math.max(0, scrollTicks + ((x - LABEL_WIDTH) / pxPerBeat) * ppq)
  const grid = Math.max(1, ppq / 4)
  const snap = (value: number) => Math.max(0, Math.round(value / grid) * grid)

  const points = normalizedTempoMap(props.project)
  const bpms = points.map(point => point.bpm)
  let minimum = Math.min(...bpms)
  let maximum = Math.max(...bpms)
  if (maximum - minimum < 20) {
    const center = (maximum + minimum) / 2
    minimum = center - 10
    maximum = center + 10
  } else {
    const padding = (maximum - minimum) * 0.18
    minimum -= padding
    maximum += padding
  }
  minimum = Math.max(20, minimum)
  maximum = Math.min(320, maximum)
  const yForBpm = (bpm: number) => 8 + (maximum - bpm) / Math.max(1, maximum - minimum) * (HEIGHT - 18)
  const bpmForY = (y: number) => clampBpm(maximum - ((y - 8) / (HEIGHT - 18)) * Math.max(1, maximum - minimum))

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const parent = canvas.parentElement!
    const draw = () => {
      const rect = parent.getBoundingClientRect()
      const dpr = window.devicePixelRatio || 1
      canvas.width = Math.max(1, Math.floor(rect.width * dpr))
      canvas.height = Math.max(1, Math.floor(rect.height * dpr))
      canvas.style.width = `${rect.width}px`
      canvas.style.height = `${rect.height}px`
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.save(); ctx.scale(dpr, dpr)
      const width = rect.width
      ctx.fillStyle = '#0e111a'; ctx.fillRect(0, 0, width, HEIGHT)
      const visibleEnd = scrollTicks + ((width - LABEL_WIDTH) / pxPerBeat) * ppq + ppq
      const barTicks = musicalBarTicks(props.project)
      for (let t = Math.floor(scrollTicks / grid) * grid; t < visibleEnd; t += grid) {
        const x = xForTick(t)
        ctx.strokeStyle = t % barTicks === 0 ? '#3c4563' : t % ppq === 0 ? '#283046' : '#202638'
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, HEIGHT); ctx.stroke()
      }
      ctx.strokeStyle = '#4b5575'
      ctx.beginPath(); ctx.moveTo(0, HEIGHT - .5); ctx.lineTo(width, HEIGHT - .5); ctx.stroke()

      const start = Math.max(0, scrollTicks - ppq)
      const end = visibleEnd
      ctx.strokeStyle = '#ffbe55'
      ctx.lineWidth = 1.8
      ctx.beginPath()
      const boundaries = [start, ...points.map(point => point.ticks).filter(tick => tick > start && tick < end), end]
      for (let index = 0; index < boundaries.length - 1; index++) {
        const segmentStart = boundaries[index]
        const segmentEnd = boundaries[index + 1]
        const y = yForBpm(bpmAt(props.project, segmentStart + 0.001))
        const x1 = xForTick(segmentStart)
        const x2 = xForTick(segmentEnd)
        if (index === 0) ctx.moveTo(x1, y)
        else ctx.lineTo(x1, y)
        ctx.lineTo(x2, y)
      }
      ctx.stroke()
      ctx.lineWidth = 1

      for (const point of points) {
        const x = xForTick(point.ticks)
        if (x < LABEL_WIDTH - 8 || x > width + 8) continue
        const y = yForBpm(point.bpm)
        const selected = selectedTick === point.ticks
        ctx.fillStyle = point.ticks === 0 ? '#71dcff' : '#ffbe55'
        ctx.strokeStyle = selected ? '#ffffff' : '#161a26'
        ctx.beginPath(); ctx.arc(x, y, selected ? 5.5 : 4.5, 0, Math.PI * 2); ctx.fill(); ctx.stroke()
        ctx.fillStyle = selected ? '#ffffff' : '#ffd58a'
        ctx.font = '9px Inter'
        ctx.fillText(`${point.bpm.toFixed(1)}`, x + 7, y + 3)
      }

      const playheadX = xForTick(props.playheadTicks)
      if (playheadX >= LABEL_WIDTH && playheadX < width) {
        ctx.strokeStyle = '#ff4f78'
        ctx.lineWidth = 1.4
        ctx.beginPath(); ctx.moveTo(playheadX, 0); ctx.lineTo(playheadX, HEIGHT); ctx.stroke()
        ctx.lineWidth = 1
      }

      ctx.fillStyle = '#151927'; ctx.fillRect(0, 0, LABEL_WIDTH, HEIGHT)
      ctx.strokeStyle = '#333b54'; ctx.beginPath(); ctx.moveTo(LABEL_WIDTH - .5, 0); ctx.lineTo(LABEL_WIDTH - .5, HEIGHT); ctx.stroke()
      ctx.fillStyle = '#aeb7d4'; ctx.font = '10px Inter'; ctx.fillText('TEMPO', 9, 18)
      ctx.fillStyle = '#6f7b9d'; ctx.font = '8px Inter'; ctx.fillText(`${props.project.bpm.toFixed(1)} BPM`, 8, 34)
      ctx.restore()
    }
    draw()
    const observer = new ResizeObserver(draw)
    observer.observe(parent)
    return () => observer.disconnect()
  }, [props.project, props.playheadTicks, scrollTicks, pxPerBeat, selectedTick, ppq, grid, points, minimum, maximum])

  function pointer(event: React.PointerEvent) {
    const rect = canvasRef.current!.getBoundingClientRect()
    return { x: event.clientX - rect.left, y: event.clientY - rect.top }
  }

  function pointHit(x: number, y: number) {
    let best: { ticks: number; bpm: number; distance: number } | null = null
    for (const point of normalizedTempoMap(props.project)) {
      const distance = Math.hypot(xForTick(point.ticks) - x, yForBpm(point.bpm) - y)
      if (distance <= 9 && (!best || distance < best.distance)) best = { ticks: point.ticks, bpm: point.bpm, distance }
    }
    return best
  }

  function upsertPoint(project: Project, originalTick: number | null, ticks: number, bpm: number) {
    const next = sortedPositivePoints(project).filter(point => point.ticks !== originalTick && point.ticks !== ticks)
    next.push({ ticks, bpm: clampBpm(bpm) })
    writePositivePoints(project, next)
  }

  function onPointerDown(event: React.PointerEvent) {
    const pos = pointer(event)
    if (pos.x < LABEL_WIDTH) return
    const hit = pointHit(pos.x, pos.y)
    if (event.button === 2) {
      if (hit && hit.ticks > 0) {
        props.updateProject(project => {
          writePositivePoints(project, sortedPositivePoints(project).filter(point => point.ticks !== hit.ticks))
        }, false)
        setSelectedTick(null)
      }
      return
    }
    if (event.button !== 0) return
    props.beginTransaction()
    if (hit) {
      dragRef.current = { originalTick: hit.ticks, originalBpm: hit.bpm, startX: pos.x, startY: pos.y, anchor: hit.ticks === 0 }
      setSelectedTick(hit.ticks)
    } else {
      const ticks = Math.max(grid, snap(tickForX(pos.x)))
      const bpm = clampBpm(bpmForY(pos.y))
      props.updateProject(project => upsertPoint(project, null, ticks, bpm), true)
      dragRef.current = { originalTick: ticks, originalBpm: bpm, startX: pos.x, startY: pos.y, anchor: false }
      setSelectedTick(ticks)
    }
    canvasRef.current?.setPointerCapture(event.pointerId)
  }

  function onPointerMove(event: React.PointerEvent) {
    const pos = pointer(event)
    const drag = dragRef.current
    if (!drag) {
      if (canvasRef.current) canvasRef.current.style.cursor = pointHit(pos.x, pos.y) ? 'grab' : pos.x >= LABEL_WIDTH ? 'copy' : 'default'
      return
    }
    if (canvasRef.current) canvasRef.current.style.cursor = 'grabbing'
    const deltaTicks = ((pos.x - drag.startX) / pxPerBeat) * ppq
    const deltaBpm = -(pos.y - drag.startY) * 0.45
    const nextBpm = clampBpm(drag.originalBpm + deltaBpm)
    props.updateProject(project => {
      if (drag.anchor) {
        project.bpm = nextBpm
        writePositivePoints(project, sortedPositivePoints(project))
      } else {
        const ticks = Math.max(grid, snap(drag.originalTick + deltaTicks))
        upsertPoint(project, drag.originalTick, ticks, nextBpm)
        setSelectedTick(ticks)
      }
    }, true)
  }

  function onPointerUp(event: React.PointerEvent) {
    if (dragRef.current) {
      dragRef.current = null
      props.endTransaction()
    }
    canvasRef.current?.releasePointerCapture(event.pointerId)
  }

  const selectedPoint = selectedTick === 0
    ? { ticks: 0, bpm: props.project.bpm }
    : sortedPositivePoints(props.project).find(point => point.ticks === selectedTick) || null

  function editSelected(ticks: number, bpm: number) {
    if (!selectedPoint) return
    props.updateProject(project => {
      if (selectedPoint.ticks === 0) {
        project.bpm = clampBpm(bpm)
      } else {
        upsertPoint(project, selectedPoint.ticks, Math.max(grid, snap(ticks)), clampBpm(bpm))
      }
    }, false)
    if (selectedPoint.ticks !== 0) setSelectedTick(Math.max(grid, snap(ticks)))
  }

  function onWheel(event: React.WheelEvent) {
    if (event.ctrlKey || event.metaKey) {
      props.onTimelineChange({ ...props.timeline, pxPerBeat: Math.max(32, Math.min(360, pxPerBeat * (event.deltaY > 0 ? .9 : 1.1))) })
    } else {
      props.onTimelineChange({ ...props.timeline, scrollTicks: Math.max(0, scrollTicks + event.deltaY * 2 + event.deltaX * 2) })
    }
  }

  return (
    <div className="tempo-lane" onContextMenu={event => event.preventDefault()}>
      <canvas ref={canvasRef} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onWheel={onWheel} />
      {selectedPoint && (
        <div className="tempo-editor">
          <label>Tick
            <input
              type="number"
              min={selectedPoint.ticks === 0 ? 0 : grid}
              step={grid}
              value={selectedPoint.ticks}
              disabled={selectedPoint.ticks === 0}
              onChange={event => editSelected(Number(event.target.value) || selectedPoint.ticks, selectedPoint.bpm)}
            />
          </label>
          <label>BPM
            <input
              type="number"
              min={MIN_BPM}
              max={MAX_BPM}
              step="0.1"
              value={selectedPoint.bpm}
              onChange={event => editSelected(selectedPoint.ticks, Number(event.target.value) || selectedPoint.bpm)}
            />
          </label>
          {selectedPoint.ticks > 0 && <button onClick={() => {
            props.updateProject(project => {
              writePositivePoints(project, sortedPositivePoints(project).filter(point => point.ticks !== selectedPoint.ticks))
            }, false)
            setSelectedTick(null)
          }}>Delete</button>}
        </div>
      )}
    </div>
  )
}
