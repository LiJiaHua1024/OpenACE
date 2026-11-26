import { useCallback, useEffect, useRef, useState } from 'react'
import type { EnvelopePoint, Project, TimelineState, Track } from '../types'

const LANE_HEIGHT = 148
const KEY_WIDTH = 64

type LaneKey = 'pitch_cents' | 'dynamic' | 'air' | 'falsetto' | 'tension' | 'energy'
type Tab = 'breath' | 'dynamic' | 'advanced' | 'pitch'

interface Props {
  project: Project
  track?: Track
  beginTransaction(): void
  endTransaction(): void
  updateProject(mutator: (project: Project) => void, transient?: boolean): void
  timeline: TimelineState
}

function clonePoints(points: EnvelopePoint[]) {
  return points.map(p => ({ ...p }))
}

export default function AutomationLane(props: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [tab, setTab] = useState<Tab>('dynamic')
  const [lane, setLane] = useState<LaneKey>('dynamic')
  const [tool, setTool] = useState<'brush' | 'line' | 'erase'>('brush')
  const dragRef = useRef<{ drawing: boolean; startTick: number; startValue: number; lineStart?: EnvelopePoint }>({ drawing: false, startTick: 0, startValue: 0 })
  const ppq = props.project.ppq

  const xForTick = useCallback((ticks: number) => KEY_WIDTH + ((ticks - props.timeline.scrollTicks) / ppq) * props.timeline.pxPerBeat, [props.timeline, ppq])
  const tickForX = useCallback((x: number) => Math.max(0, Math.round(props.timeline.scrollTicks + ((x - KEY_WIDTH) / props.timeline.pxPerBeat) * ppq)), [props.timeline, ppq])
  const maxValue = lane === 'pitch_cents' ? 100 : 1
  const minValue = lane === 'pitch_cents' ? -100 : 0

  function pointsFor(track: Track, key: LaneKey): EnvelopePoint[] {
    return (track.automation as any)[key] || []
  }

  function upsertPoint(points: EnvelopePoint[], point: EnvelopePoint) {
    const existing = points.findIndex(p => Math.abs(p.ticks - point.ticks) < 20)
    if (existing >= 0) points[existing] = point
    else points.push(point)
    points.sort((a, b) => a.ticks - b.ticks)
  }

  function writeLanePoint(tick: number, value: number, erase = false) {
    if (!props.track) return
    const trackId = props.track.id
    props.updateProject(project => {
      const track = project.tracks.find(t => t.id === trackId)
      if (!track) return
      const points = clonePoints(pointsFor(track, lane))
      if (erase) {
        const index = points.findIndex(p => Math.abs(p.ticks - tick) < 35)
        if (index >= 0) points.splice(index, 1)
      } else {
        upsertPoint(points, { ticks: Math.round(tick), value, curve: 'linear' })
      }
      ;(track.automation as any)[lane] = points
    }, true)
  }

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
      ctx.save()
      ctx.scale(dpr, dpr)
      const width = rect.width
      const height = rect.height
      ctx.fillStyle = '#11131d'
      ctx.fillRect(0, 0, width, height)
      const barTicks = ppq * props.project.time_signature.numerator
      const endTick = props.timeline.scrollTicks + ((width - KEY_WIDTH) / props.timeline.pxPerBeat) * ppq + barTicks
      const firstTick = Math.floor(props.timeline.scrollTicks / (ppq / 4)) * (ppq / 4)
      for (let t = firstTick; t < endTick; t += ppq / 4) {
        const x = xForTick(t)
        ctx.strokeStyle = t % barTicks === 0 ? '#414964' : t % ppq === 0 ? '#2c3248' : '#202536'
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, height); ctx.stroke()
      }
      ctx.fillStyle = '#171a27'
      ctx.fillRect(0, 0, KEY_WIDTH, height)
      ctx.strokeStyle = '#394056'
      ctx.beginPath(); ctx.moveTo(KEY_WIDTH - .5, 0); ctx.lineTo(KEY_WIDTH - .5, height); ctx.stroke()

      if (!props.track) {
        ctx.fillStyle = '#7f89a8'; ctx.font = '12px Inter'; ctx.fillText('Select a vocal track', 20, 28)
        ctx.restore(); return
      }

      if (tab === 'breath') {
        ctx.fillStyle = '#aeb7d4'; ctx.font = '11px Inter'; ctx.fillText('Breath / Phoneme', 10, 18)
        for (const breath of props.track.breaths) {
          const x = xForTick(breath.start_ticks)
          const w = Math.max(12, breath.duration_ticks / 2)
          ctx.fillStyle = '#7c4dffaa'
          ctx.beginPath(); ctx.roundRect(x, 34, w, 28, 4); ctx.fill()
          ctx.fillStyle = 'white'; ctx.font = '10px Inter'; ctx.fillText('BR.', x + 5, 52)
        }
        let y = 82
        for (const note of props.track.notes) {
          const x = xForTick(note.start_ticks)
          const w = Math.max(14, note.duration_ticks / 2)
          if (x > width || x + w < KEY_WIDTH) continue
          ctx.strokeStyle = '#3d465f'; ctx.strokeRect(x, y, w, 30)
          if (note.phonemes.length) {
            let cursor = x
            for (const ph of note.phonemes) {
              const pw = Math.max(8, (ph.duration_ms / Math.max(1, note.duration_ticks * 60000 / props.project.bpm / ppq)) * w)
              ctx.fillStyle = ph.is_vowel ? '#2f9e7a88' : '#4d8bd888'
              ctx.fillRect(cursor, y, pw, 30)
              ctx.fillStyle = '#eaf2ff'; ctx.font = '9px Inter'; ctx.fillText(ph.symbol, cursor + 2, y + 18)
              cursor += pw
            }
          } else {
            ctx.fillStyle = '#7f89a8'; ctx.font = '9px Inter'; ctx.fillText(note.lyric ? 'phonemes generated on validate/render' : 'no lyric', x + 3, y + 18)
          }
        }
      } else {
        const label = lane === 'pitch_cents' ? 'Pitch deviation (cents)' : lane[0].toUpperCase() + lane.slice(1)
        ctx.fillStyle = '#aeb7d4'; ctx.font = '11px Inter'; ctx.fillText(label, 10, 18)
        const points = pointsFor(props.track, lane)
        const neutral = lane === 'pitch_cents' ? height / 2 : height * 0.58
        ctx.strokeStyle = '#6d748c'; ctx.setLineDash([4, 5]); ctx.beginPath(); ctx.moveTo(KEY_WIDTH, neutral); ctx.lineTo(width, neutral); ctx.stroke(); ctx.setLineDash([])
        if (!points.length) {
          ctx.fillStyle = '#65708e'; ctx.font = '12px Inter'; ctx.fillText('AUTO', KEY_WIDTH + 18, neutral - 10)
        }
        const yForValue = (value: number) => {
          if (lane === 'pitch_cents') return height / 2 - (value / 100) * (height * 0.38)
          return height - 18 - value * (height - 42)
        }
        ctx.strokeStyle = '#64e3ff'; ctx.lineWidth = 1.8
        ctx.beginPath()
        points.forEach((p, i) => {
          const x = xForTick(p.ticks)
          const y = yForValue(p.value)
          if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
        })
        ctx.stroke()
        for (const p of points) {
          ctx.fillStyle = '#d9f7ff'
          ctx.beginPath(); ctx.arc(xForTick(p.ticks), yForValue(p.value), 3.3, 0, Math.PI * 2); ctx.fill()
        }
      }
      ctx.restore()
    }
    draw()
    const observer = new ResizeObserver(draw)
    observer.observe(parent)
    return () => observer.disconnect()
  }, [props.project, props.track, props.timeline, tab, lane, ppq, xForTick])

  function pointer(event: React.PointerEvent) {
    const rect = canvasRef.current!.getBoundingClientRect()
    return { x: event.clientX - rect.left, y: event.clientY - rect.top, height: rect.height }
  }

  function valueForY(y: number, height: number) {
    if (lane === 'pitch_cents') return Math.max(minValue, Math.min(maxValue, ((height / 2 - y) / (height * 0.38)) * 100))
    return Math.max(0, Math.min(1, (height - 18 - y) / (height - 42)))
  }

  function onPointerDown(event: React.PointerEvent) {
    if (!props.track) return
    const pos = pointer(event)
    const tick = tickForX(pos.x)
    props.beginTransaction()
    if (tab === 'breath') {
      if (event.button === 0 && pos.y > 28 && pos.y < 68) {
        props.updateProject(project => {
          const track = project.tracks.find(t => t.id === props.track!.id)
          track?.breaths.push({ id: `br_${crypto.randomUUID().slice(0, 8)}`, start_ticks: tick, duration_ticks: ppq / 4 })
        }, true)
      }
      props.endTransaction()
      return
    }
    const value = valueForY(pos.y, pos.height)
    dragRef.current = { drawing: true, startTick: tick, startValue: value, lineStart: { ticks: tick, value, curve: 'linear' } }
    if (tool !== 'line') writeLanePoint(tick, value, tool === 'erase')
    canvasRef.current?.setPointerCapture(event.pointerId)
  }

  function onPointerMove(event: React.PointerEvent) {
    if (!dragRef.current.drawing || tab === 'breath') return
    const pos = pointer(event)
    if (tool === 'line') return
    writeLanePoint(tickForX(pos.x), valueForY(pos.y, pos.height), tool === 'erase')
  }

  function onPointerUp(event: React.PointerEvent) {
    if (dragRef.current.drawing && tool === 'line' && dragRef.current.lineStart) {
      const pos = pointer(event)
      const endTick = tickForX(pos.x)
      const endValue = valueForY(pos.y, pos.height)
      writeLanePoint(dragRef.current.lineStart.ticks, dragRef.current.lineStart.value, false)
      writeLanePoint(endTick, endValue, false)
    }
    if (dragRef.current.drawing) props.endTransaction()
    dragRef.current.drawing = false
    canvasRef.current?.releasePointerCapture(event.pointerId)
  }

  function addAllBreaths() {
    if (!props.track) return
    props.beginTransaction()
    props.updateProject(project => {
      const track = project.tracks.find(t => t.id === props.track!.id)
      if (!track) return
      track.breaths = []
      let previousEnd = 0
      for (const note of track.notes) {
        if (note.start_ticks - previousEnd >= ppq) {
          track.breaths.push({ id: `br_${crypto.randomUUID().slice(0, 8)}`, start_ticks: previousEnd + Math.floor((note.start_ticks - previousEnd) / 2), duration_ticks: ppq / 4 })
        }
        previousEnd = Math.max(previousEnd, note.start_ticks + note.duration_ticks)
      }
    }, true)
    props.endTransaction()
  }

  const advancedButton = (key: LaneKey, label: string) => (
    <button className={lane === key ? 'param-tab active' : 'param-tab'} onClick={() => { setTab(key === 'pitch_cents' ? 'pitch' : key === 'dynamic' ? 'dynamic' : 'advanced'); setLane(key) }}>{label}</button>
  )

  return (
    <section className="automation-panel">
      <div className="automation-header">
        <div className="tool-group">
          <button className={tab === 'breath' ? 'param-tab active' : 'param-tab'} onClick={() => setTab('breath')}>Breath & Phoneme</button>
          {advancedButton('dynamic', 'Dynamic')}
          {advancedButton('pitch_cents', 'Pitch')}
          {advancedButton('air', 'Air')}
          {advancedButton('falsetto', 'Falsetto')}
          {advancedButton('tension', 'Tension')}
          {advancedButton('energy', 'Energy')}
        </div>
        {tab === 'breath' ? (
          <button className="tiny-button" onClick={addAllBreaths}>Add all breaths</button>
        ) : (
          <div className="tool-group">
            <button className={tool === 'brush' ? 'tool active' : 'tool'} onClick={() => setTool('brush')}>Brush</button>
            <button className={tool === 'line' ? 'tool active' : 'tool'} onClick={() => setTool('line')}>Line</button>
            <button className={tool === 'erase' ? 'tool active' : 'tool'} onClick={() => setTool('erase')}>Erase</button>
          </div>
        )}
      </div>
      <div className="automation-canvas-wrap">
        <canvas ref={canvasRef} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onContextMenu={e => e.preventDefault()} />
      </div>
    </section>
  )
}
