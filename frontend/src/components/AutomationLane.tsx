import { useCallback, useEffect, useRef, useState } from 'react'
import type { EnvelopePoint, Note, Phoneme, Project, TimelineState, Track } from '../types'
import { tickDurationSeconds } from '../tempo'

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
  const phonemeDragRef = useRef<{
    noteId: string
    edge: 'start' | 'between' | 'end'
    index: number
    startX: number
    originalBoundary: number
    originals: Phoneme[]
    pxPerMs: number
    durationMs: number
  } | null>(null)
  const [phonemeReadout, setPhonemeReadout] = useState('')
  const ppq = props.project.ppq

  const xForTick = useCallback((ticks: number) => KEY_WIDTH + ((ticks - props.timeline.scrollTicks) / ppq) * props.timeline.pxPerBeat, [props.timeline, ppq])
  const tickForX = useCallback((x: number) => Math.max(0, Math.round(props.timeline.scrollTicks + ((x - KEY_WIDTH) / props.timeline.pxPerBeat) * ppq)), [props.timeline, ppq])
  const maxValue = lane === 'pitch_cents' ? 100 : 1
  const minValue = lane === 'pitch_cents' ? -100 : 0

  function pointsFor(track: Track, key: LaneKey): EnvelopePoint[] {
    return (track.automation as any)[key] || []
  }

  function noteDurationMs(note: Note) {
    return Math.max(1, tickDurationSeconds(props.project, note.start_ticks, note.duration_ticks) * 1000)
  }

  function noteLayout(note: Note) {
    const x = xForTick(note.start_ticks)
    const w = Math.max(14, (note.duration_ticks / ppq) * props.timeline.pxPerBeat)
    return { x, w, durationMs: noteDurationMs(note), pxPerMs: w / noteDurationMs(note) }
  }

  function phonemeBoundaryHit(x: number, y: number) {
    if (!props.track || y < 82 || y > 112) return null
    let best: { note: Note; edge: 'start' | 'between' | 'end'; index: number; boundaryMs: number; distance: number } | null = null
    for (const note of props.track.notes) {
      if (note.phonemes.length < 1) continue
      const layout = noteLayout(note)
      const candidates: { edge: 'start' | 'between' | 'end'; index: number; boundaryMs: number }[] = []
      const first = note.phonemes[0]
      const last = note.phonemes[note.phonemes.length - 1]
      candidates.push({ edge: 'start', index: 0, boundaryMs: first.start_ms })
      for (let index = 0; index < note.phonemes.length - 1; index++) {
        candidates.push({ edge: 'between', index, boundaryMs: note.phonemes[index].start_ms + note.phonemes[index].duration_ms })
      }
      candidates.push({ edge: 'end', index: note.phonemes.length - 1, boundaryMs: last.start_ms + last.duration_ms })
      for (const candidate of candidates) {
        const next = note.phonemes[candidate.index + 1]
        const anchoredVowelBoundary = candidate.edge === 'start'
          ? first.is_vowel && Math.abs(first.start_ms) < 0.75
          : candidate.edge === 'between' && next?.is_vowel && Math.abs(next.start_ms) < 0.75
        if (anchoredVowelBoundary) continue
        const bx = layout.x + candidate.boundaryMs * layout.pxPerMs
        const distance = Math.abs(bx - x)
        if (distance <= 7 && (!best || distance < best.distance)) {
          best = { note, edge: candidate.edge, index: candidate.index, boundaryMs: candidate.boundaryMs, distance }
        }
      }
    }
    return best
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
      const pixelWidth = Math.max(1, Math.floor(rect.width * dpr))
      const pixelHeight = Math.max(1, Math.floor(rect.height * dpr))
      if (canvas.width !== pixelWidth) canvas.width = pixelWidth
      if (canvas.height !== pixelHeight) canvas.height = pixelHeight
      if (canvas.style.width !== `${rect.width}px`) canvas.style.width = `${rect.width}px`
      if (canvas.style.height !== `${rect.height}px`) canvas.style.height = `${rect.height}px`
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
        const y = 82
        for (const note of props.track.notes) {
          const layout = noteLayout(note)
          const { x, w } = layout
          if (x > width || x + w < KEY_WIDTH) continue
          ctx.strokeStyle = '#3d465f'; ctx.strokeRect(x, y, w, 30)
          if (note.phonemes.length) {
            for (const ph of note.phonemes) {
              const px = x + ph.start_ms * layout.pxPerMs
              const pw = Math.max(2, ph.duration_ms * layout.pxPerMs)
              ctx.fillStyle = ph.is_vowel ? '#2f9e7a88' : '#4d8bd888'
              ctx.fillRect(px, y, pw, 30)
              ctx.fillStyle = '#eaf2ff'; ctx.font = '9px Inter'
              if (pw > 9) ctx.fillText(ph.symbol, px + 2, y + 18)
            }
            const first = note.phonemes[0]
            const last = note.phonemes[note.phonemes.length - 1]
            const outer = [
              { ms: first.start_ms, locked: first.is_vowel && Math.abs(first.start_ms) < 0.75 },
              { ms: last.start_ms + last.duration_ms, locked: false },
            ]
            for (const edge of outer) {
              const ex = x + edge.ms * layout.pxPerMs
              ctx.strokeStyle = edge.locked ? '#ffffffdd' : '#d8e7ff99'
              ctx.lineWidth = edge.locked ? 1.5 : 1
              ctx.beginPath(); ctx.moveTo(ex, y); ctx.lineTo(ex, y + 30); ctx.stroke()
              if (!edge.locked) {
                ctx.fillStyle = '#eaf2ffcc'
                ctx.fillRect(ex - 1.5, y + 25, 3, 5)
              }
            }
            for (let index = 0; index < note.phonemes.length - 1; index++) {
              const left = note.phonemes[index]
              const right = note.phonemes[index + 1]
              const boundaryMs = left.start_ms + left.duration_ms
              const bx = x + boundaryMs * layout.pxPerMs
              const locked = right.is_vowel && Math.abs(right.start_ms) < 0.75
              ctx.strokeStyle = locked ? '#ffffffdd' : '#d8e7ff99'
              ctx.lineWidth = locked ? 1.5 : 1
              ctx.beginPath(); ctx.moveTo(bx, y); ctx.lineTo(bx, y + 30); ctx.stroke()
              if (!locked) {
                ctx.fillStyle = '#eaf2ffcc'
                ctx.fillRect(bx - 1.5, y + 25, 3, 5)
              }
            }
          } else {
            ctx.fillStyle = '#7f89a8'; ctx.font = '9px Inter'; ctx.fillText(note.lyric ? 'phonemes generated on validate/render' : 'no lyric', x + 3, y + 18)
          }
        }
      } else {
        const label = lane === 'pitch_cents' ? 'Pitch deviation (cents)' : lane[0].toUpperCase() + lane.slice(1)
        ctx.fillStyle = '#aeb7d4'; ctx.font = '11px Inter'; ctx.fillText(label, 10, 18)
        const points = pointsFor(props.track, lane)
        const neutral = lane === 'pitch_cents' ? height / 2 : height - 18 - 0.5 * (height - 42)
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
      const boundaryHit = event.button === 0 ? phonemeBoundaryHit(pos.x, pos.y) : null
      if (boundaryHit) {
        const layout = noteLayout(boundaryHit.note)
        phonemeDragRef.current = {
          noteId: boundaryHit.note.id,
          edge: boundaryHit.edge,
          index: boundaryHit.index,
          startX: pos.x,
          originalBoundary: boundaryHit.boundaryMs,
          originals: JSON.parse(JSON.stringify(boundaryHit.note.phonemes)),
          pxPerMs: layout.pxPerMs,
          durationMs: layout.durationMs,
        }
        canvasRef.current?.setPointerCapture(event.pointerId)
        return
      }
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
    const pos = pointer(event)
    const phonemeDrag = phonemeDragRef.current
    if (phonemeDrag) {
      const deltaMs = (pos.x - phonemeDrag.startX) / phonemeDrag.pxPerMs
      const minimum = 8
      props.updateProject(project => {
        const note = project.tracks.find(t => t.id === props.track?.id)?.notes.find(item => item.id === phonemeDrag.noteId)
        if (!note) return
        const phonemes: Phoneme[] = JSON.parse(JSON.stringify(phonemeDrag.originals))
        if (phonemeDrag.edge === 'between') {
          const left = phonemes[phonemeDrag.index]
          const right = phonemes[phonemeDrag.index + 1]
          if (!left || !right) return
          const rightEnd = right.start_ms + right.duration_ms
          const boundary = Math.max(left.start_ms + minimum, Math.min(rightEnd - minimum, phonemeDrag.originalBoundary + deltaMs))
          left.duration_ms = boundary - left.start_ms
          right.start_ms = boundary
          right.duration_ms = rightEnd - boundary
          setPhonemeReadout(`${left.symbol}/${right.symbol} · ${Math.round(boundary)} ms`)
        } else if (phonemeDrag.edge === 'start') {
          const first = phonemes[0]
          if (!first) return
          const fixedEnd = first.start_ms + first.duration_ms
          const lower = first.is_vowel ? 0 : -90
          const upper = first.is_vowel ? 0 : Math.min(-40, fixedEnd - minimum)
          const start = Math.max(lower, Math.min(upper, phonemeDrag.originalBoundary + deltaMs))
          first.start_ms = start
          first.duration_ms = fixedEnd - start
          setPhonemeReadout(`${first.symbol} onset · ${Math.round(start)} ms`)
        } else {
          const last = phonemes[phonemeDrag.index]
          if (!last) return
          const end = Math.max(last.start_ms + minimum, Math.min(phonemeDrag.durationMs, phonemeDrag.originalBoundary + deltaMs))
          last.duration_ms = end - last.start_ms
          setPhonemeReadout(`${last.symbol} end · ${Math.round(end)} ms`)
        }
        note.phonemes = phonemes
      }, true)
      return
    }
    if (tab === 'breath') {
      if (canvasRef.current) canvasRef.current.style.cursor = phonemeBoundaryHit(pos.x, pos.y) ? 'col-resize' : 'default'
      return
    }
    if (!dragRef.current.drawing) return
    if (tool === 'line') return
    writeLanePoint(tickForX(pos.x), valueForY(pos.y, pos.height), tool === 'erase')
  }

  function onPointerUp(event: React.PointerEvent) {
    if (phonemeDragRef.current) {
      phonemeDragRef.current = null
      props.endTransaction()
      window.setTimeout(() => setPhonemeReadout(''), 1600)
    }
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
          <div className="breath-actions">
            <span className="phoneme-readout">{phonemeReadout}</span>
            <button className="tiny-button" onClick={addAllBreaths}>Add all breaths</button>
          </div>
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
