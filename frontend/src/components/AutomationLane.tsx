import { useCallback, useEffect, useRef, useState } from 'react'
import type { Breath, BreathTimbre, EnvelopePoint, Note, Phoneme, Project, TimelineState, Track } from '../types'
import { barTicks as musicalBarTicks, tickDurationSeconds } from '../tempo'

const LANE_HEIGHT = 148
const KEY_WIDTH = 64

type LaneKey = 'pitch_cents' | 'dynamic' | 'air' | 'falsetto' | 'tension' | 'energy' | 'volume' | 'pan'
type Tab = 'breath' | 'dynamic' | 'advanced' | 'pitch'

interface Props {
  project: Project
  track?: Track
  playheadTicks: number
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
  const breathDragRef = useRef<{
    id: string
    mode: 'move' | 'resize-start' | 'resize-end'
    startX: number
    originalStart: number
    originalDuration: number
  } | null>(null)
  const [phonemeReadout, setPhonemeReadout] = useState('')
  const [selectedBreathId, setSelectedBreathId] = useState<string | null>(null)
  const [selection, setSelection] = useState<{ start: number; end: number } | null>(null)
  const selectionDragRef = useRef<{ anchorTicks: number; startX: number; moved: boolean } | null>(null)
  const automationClipboardRef = useRef<{ lane: LaneKey; spanTicks: number; points: { deltaTicks: number; value: number; curve: string }[] } | null>(null)
  const [, setAutomationClipboardVersion] = useState(0)
  const ppq = props.project.ppq
  const snapGrid = Math.max(1, Math.round(ppq / Math.max(1, props.timeline.gridDivision ?? 4)))

  const xForTick = useCallback((ticks: number) => KEY_WIDTH + ((ticks - props.timeline.scrollTicks) / ppq) * props.timeline.pxPerBeat, [props.timeline, ppq])
  const tickForX = useCallback((x: number) => Math.max(0, Math.round(props.timeline.scrollTicks + ((x - KEY_WIDTH) / props.timeline.pxPerBeat) * ppq)), [props.timeline, ppq])
  function laneRange(key: LaneKey = lane): [number, number] {
    if (key === 'pitch_cents') return [-600, 600]
    if (key === 'pan') return [-1, 1]
    return [0, 1]
  }
  const [minValue, maxValue] = laneRange()

  function pointsFor(track: Track, key: LaneKey): EnvelopePoint[] {
    return (track.automation as any)[key] || []
  }

  function automationValueAt(points: EnvelopePoint[], ticks: number) {
    if (!points.length) {
      if (lane === 'pitch_cents') return 0
      if (lane === 'pan') return props.track?.pan ?? 0
      if (lane === 'volume') return props.track?.volume ?? 0.8
      return 0.5
    }
    const ordered = [...points].sort((a, b) => a.ticks - b.ticks)
    if (ticks <= ordered[0].ticks) return ordered[0].value
    if (ticks >= ordered[ordered.length - 1].ticks) return ordered[ordered.length - 1].value
    for (let index = 0; index < ordered.length - 1; index++) {
      const left = ordered[index]
      const right = ordered[index + 1]
      if (ticks >= left.ticks && ticks <= right.ticks) {
        const ratio = (ticks - left.ticks) / Math.max(1e-9, right.ticks - left.ticks)
        return left.value + (right.value - left.value) * ratio
      }
    }
    return ordered[ordered.length - 1].value
  }

  function laneFallbackValue() {
    if (lane === 'pitch_cents') return 0
    if (lane === 'pan') return props.track?.pan ?? 0
    if (lane === 'volume') return props.track?.volume ?? 0.8
    return 0.5
  }

  function yForLaneValue(value: number, height: number) {
    const [minimum, maximum] = laneRange()
    if (minimum < 0) {
      const scale = Math.max(Math.abs(minimum), Math.abs(maximum))
      return height / 2 - (value / scale) * (height * 0.38)
    }
    return height - 18 - ((value - minimum) / Math.max(1e-9, maximum - minimum)) * (height - 42)
  }

  function noteDurationMs(note: Note) {
    return Math.max(1, tickDurationSeconds(props.project, note.start_ticks, note.duration_ticks) * 1000)
  }

  function noteLayout(note: Note) {
    const x = xForTick(note.start_ticks)
    const w = Math.max(14, (note.duration_ticks / ppq) * props.timeline.pxPerBeat)
    return { x, w, durationMs: noteDurationMs(note), pxPerMs: w / noteDurationMs(note) }
  }

  function breathHit(x: number, y: number) {
    if (!props.track || y < 28 || y > 68) return null
    for (let index = props.track.breaths.length - 1; index >= 0; index--) {
      const breath = props.track.breaths[index]
      const bx = xForTick(breath.start_ticks)
      const bw = Math.max(10, (breath.duration_ticks / ppq) * props.timeline.pxPerBeat)
      if (x < bx || x > bx + bw) continue
      const edgeDistance = Math.min(Math.abs(x - bx), Math.abs(x - (bx + bw)))
      return {
        breath,
        mode: edgeDistance <= 5 ? (Math.abs(x - bx) < Math.abs(x - (bx + bw)) ? 'resize-start' as const : 'resize-end' as const) : 'move' as const,
      }
    }
    return null
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
      const barTicks = musicalBarTicks(props.project)
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
          const w = Math.max(10, (breath.duration_ticks / ppq) * props.timeline.pxPerBeat)
          const intensity = Math.max(0, Math.min(2, breath.intensity ?? 1))
          const timbre = breath.timbre || 'natural'
          const color = timbre === 'soft' ? '96, 181, 255' : timbre === 'strong' ? '255, 143, 90' : '124, 77, 255'
          const selected = selectedBreathId === breath.id
          ctx.fillStyle = `rgba(${color}, ${0.42 + intensity * 0.18})`
          ctx.beginPath(); ctx.roundRect(x, 34, w, 28, 4); ctx.fill()
          if (selected) {
            ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 1.5
            ctx.beginPath(); ctx.roundRect(x + 0.5, 34.5, w - 1, 27, 4); ctx.stroke()
            ctx.lineWidth = 1
          }
          const meterHeight = Math.max(2, intensity * 8)
          ctx.fillStyle = '#ffffffcc'; ctx.fillRect(x + w - 3, 57 - meterHeight, 2, meterHeight)
          ctx.fillStyle = 'white'; ctx.font = '10px Inter'
          if (w > 34) ctx.fillText(`BR ${Math.round(intensity * 100)}%`, x + 5, 52)
          else ctx.fillText('BR.', x + 4, 52)
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
        const label = lane === 'pitch_cents' ? 'Pitch deviation (cents)' : lane === 'volume' ? 'Track volume automation (absolute)' : lane === 'pan' ? 'Track pan automation (absolute)' : lane[0].toUpperCase() + lane.slice(1)
        ctx.fillStyle = '#aeb7d4'; ctx.font = '11px Inter'; ctx.fillText(label, 10, 18)
        const points = pointsFor(props.track, lane)
        if (selection && selection.end > selection.start) {
          const sx = xForTick(selection.start)
          const ex = xForTick(selection.end)
          ctx.fillStyle = '#55c7ff20'
          ctx.fillRect(sx, 0, ex - sx, height)
          ctx.strokeStyle = '#61d5ffaa'
          ctx.beginPath(); ctx.moveTo(sx, 0); ctx.lineTo(sx, height); ctx.moveTo(ex, 0); ctx.lineTo(ex, height); ctx.stroke()
        }
        const neutral = yForLaneValue(laneFallbackValue(), height)
        ctx.strokeStyle = '#6d748c'; ctx.setLineDash([4, 5]); ctx.beginPath(); ctx.moveTo(KEY_WIDTH, neutral); ctx.lineTo(width, neutral); ctx.stroke(); ctx.setLineDash([])
        if (!points.length) {
          ctx.fillStyle = '#65708e'; ctx.font = '12px Inter'; ctx.fillText('AUTO', KEY_WIDTH + 18, neutral - 10)
        }
        const yForValue = (value: number) => yForLaneValue(value, height)
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
  }, [props.project, props.track, props.timeline, tab, lane, ppq, xForTick, selectedBreathId, selection])

  function pointer(event: React.PointerEvent) {
    const rect = canvasRef.current!.getBoundingClientRect()
    return { x: event.clientX - rect.left, y: event.clientY - rect.top, height: rect.height }
  }

  function valueForY(y: number, height: number) {
    const [minimum, maximum] = laneRange()
    let value: number
    if (minimum < 0) {
      const scale = Math.max(Math.abs(minimum), Math.abs(maximum))
      value = ((height / 2 - y) / (height * 0.38)) * scale
    } else {
      value = minimum + ((height - 18 - y) / (height - 42)) * (maximum - minimum)
    }
    return Math.max(minimum, Math.min(maximum, value))
  }

  function onPointerDown(event: React.PointerEvent) {
    if (!props.track) return
    const pos = pointer(event)
    const tick = tickForX(pos.x)
    if (tab !== 'breath' && event.button === 0 && event.shiftKey) {
      selectionDragRef.current = { anchorTicks: tick, startX: pos.x, moved: false }
      canvasRef.current?.setPointerCapture(event.pointerId)
      return
    }
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
      const hit = breathHit(pos.x, pos.y)
      if (hit && event.button === 2) {
        props.updateProject(project => {
          const track = project.tracks.find(t => t.id === props.track!.id)
          if (track) track.breaths = track.breaths.filter(item => item.id !== hit.breath.id)
        }, true)
        if (selectedBreathId === hit.breath.id) setSelectedBreathId(null)
        props.endTransaction()
        return
      }
      if (hit && event.button === 0) {
        setSelectedBreathId(hit.breath.id)
        breathDragRef.current = {
          id: hit.breath.id,
          mode: hit.mode,
          startX: pos.x,
          originalStart: hit.breath.start_ticks,
          originalDuration: hit.breath.duration_ticks,
        }
        canvasRef.current?.setPointerCapture(event.pointerId)
        return
      }
      if (event.button === 0 && pos.y > 28 && pos.y < 68) {
        const id = `br_${crypto.randomUUID().slice(0, 8)}`
        props.updateProject(project => {
          const track = project.tracks.find(t => t.id === props.track!.id)
          track?.breaths.push({ id, start_ticks: tick, duration_ticks: ppq / 4, intensity: 1, timbre: 'natural' })
        }, true)
        setSelectedBreathId(id)
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
    const selectionDrag = selectionDragRef.current
    if (selectionDrag) {
      if (Math.abs(pos.x - selectionDrag.startX) > 3) {
        selectionDrag.moved = true
        const grid = snapGrid
        const snapSelectionTick = (ticks: number) => Math.max(0, Math.round(ticks / grid) * grid)
        const current = snapSelectionTick(tickForX(pos.x))
        const anchor = snapSelectionTick(selectionDrag.anchorTicks)
        const start = Math.min(anchor, current)
        const end = Math.max(anchor, current)
        if (end - start >= grid) setSelection({ start, end })
      }
      return
    }
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
      const breathDrag = breathDragRef.current
      if (breathDrag) {
        const deltaTicks = ((pos.x - breathDrag.startX) / props.timeline.pxPerBeat) * ppq
        const grid = snapGrid
        const snap = (value: number) => Math.max(0, Math.round(value / grid) * grid)
        props.updateProject(project => {
          const track = project.tracks.find(t => t.id === props.track?.id)
          const breath = track?.breaths.find(item => item.id === breathDrag.id)
          if (!breath) return
          const originalEnd = breathDrag.originalStart + breathDrag.originalDuration
          if (breathDrag.mode === 'move') {
            breath.start_ticks = snap(breathDrag.originalStart + deltaTicks)
          } else if (breathDrag.mode === 'resize-start') {
            breath.start_ticks = Math.min(snap(breathDrag.originalStart + deltaTicks), originalEnd - grid)
            breath.duration_ticks = Math.max(grid, originalEnd - breath.start_ticks)
          } else {
            breath.duration_ticks = Math.max(grid, snap(breathDrag.originalDuration + deltaTicks))
          }
        }, true)
        if (canvasRef.current) canvasRef.current.style.cursor = breathDrag.mode === 'move' ? 'grabbing' : 'col-resize'
        return
      }
      const hit = breathHit(pos.x, pos.y)
      if (canvasRef.current) {
        canvasRef.current.style.cursor = hit ? (hit.mode === 'move' ? 'grab' : 'col-resize') : phonemeBoundaryHit(pos.x, pos.y) ? 'col-resize' : 'default'
      }
      return
    }
    if (!dragRef.current.drawing) return
    if (tool === 'line') return
    writeLanePoint(tickForX(pos.x), valueForY(pos.y, pos.height), tool === 'erase')
  }

  function onPointerUp(event: React.PointerEvent) {
    if (selectionDragRef.current) {
      if (!selectionDragRef.current.moved) setSelection(null)
      selectionDragRef.current = null
      canvasRef.current?.releasePointerCapture(event.pointerId)
      return
    }
    if (phonemeDragRef.current) {
      phonemeDragRef.current = null
      props.endTransaction()
      window.setTimeout(() => setPhonemeReadout(''), 1600)
    }
    if (breathDragRef.current) {
      breathDragRef.current = null
      props.endTransaction()
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

  function copyAutomationSelection() {
    if (!props.track || !selection || selection.end <= selection.start) return
    const source = [...pointsFor(props.track, lane)].sort((a, b) => a.ticks - b.ticks)
    const copied = new Map<number, { value: number; curve: string }>()
    copied.set(0, { value: automationValueAt(source, selection.start), curve: 'linear' })
    copied.set(selection.end - selection.start, { value: automationValueAt(source, selection.end), curve: 'linear' })
    for (const point of source) {
      if (point.ticks > selection.start && point.ticks < selection.end) copied.set(point.ticks - selection.start, { value: point.value, curve: point.curve || 'linear' })
    }
    automationClipboardRef.current = {
      lane,
      spanTicks: selection.end - selection.start,
      points: Array.from(copied.entries()).sort((a, b) => a[0] - b[0]).map(([deltaTicks, point]) => ({ deltaTicks, value: point.value, curve: point.curve })),
    }
    setAutomationClipboardVersion(version => version + 1)
  }

  function pasteAutomationClipboard() {
    const clipboard = automationClipboardRef.current
    if (!props.track || !clipboard || clipboard.lane !== lane) return
    const targetStart = Math.max(0, Math.round(props.playheadTicks / snapGrid) * snapGrid)
    const targetEnd = targetStart + clipboard.spanTicks
    const trackId = props.track.id
    props.updateProject(project => {
      const track = project.tracks.find(item => item.id === trackId)
      if (!track) return
      const kept = clonePoints(pointsFor(track, lane)).filter(point => point.ticks < targetStart || point.ticks > targetEnd)
      const pasted = clipboard.points.map(point => ({ ticks: Math.round(targetStart + point.deltaTicks), value: point.value, curve: point.curve || 'linear' }))
      ;(track.automation as any)[lane] = [...kept, ...pasted].sort((a, b) => a.ticks - b.ticks)
    }, false)
    setSelection({ start: targetStart, end: targetEnd })
  }

  function deleteAutomationSelection() {
    if (!props.track || !selection) return
    const trackId = props.track.id
    const range = selection
    props.updateProject(project => {
      const track = project.tracks.find(item => item.id === trackId)
      if (!track) return
      ;(track.automation as any)[lane] = clonePoints(pointsFor(track, lane)).filter(point => point.ticks < range.start || point.ticks > range.end)
    }, false)
  }

  const selectedBreath = props.track?.breaths.find(breath => breath.id === selectedBreathId) || null

  function updateSelectedBreath(mutator: (breath: Breath) => void, transient = true) {
    if (!props.track || !selectedBreath) return
    props.updateProject(project => {
      const breath = project.tracks.find(t => t.id === props.track!.id)?.breaths.find(item => item.id === selectedBreath.id)
      if (breath) mutator(breath)
    }, transient)
  }

  function setSelectedTimbre(timbre: BreathTimbre) {
    updateSelectedBreath(breath => { breath.timbre = timbre }, false)
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
          track.breaths.push({ id: `br_${crypto.randomUUID().slice(0, 8)}`, start_ticks: previousEnd + Math.floor((note.start_ticks - previousEnd) / 2), duration_ticks: ppq / 4, intensity: 1, timbre: 'natural' })
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
          {advancedButton('volume', 'Volume')}
          {advancedButton('pan', 'Pan')}
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
        {tab !== 'breath' && (selection || automationClipboardRef.current?.lane === lane) && (
          <div className="automation-range-actions">
            {selection && <span>{Math.round(selection.end - selection.start)}t</span>}
            {selection && <button title="Copy selected automation segment" onClick={copyAutomationSelection}>Copy</button>}
            {automationClipboardRef.current?.lane === lane && <button title="Paste copied automation at playhead" onClick={pasteAutomationClipboard}>Paste</button>}
            {selection && <button title="Delete points inside selected automation range" onClick={deleteAutomationSelection}>Delete</button>}
          </div>
        )}
        {tab === 'breath' && selectedBreath && (
          <div className="breath-inspector" title="Honest post-render shaping of real donor aspiration; not neural breath synthesis">
            <span>Intensity</span>
            <input
              type="range"
              min="0"
              max="2"
              step="0.05"
              value={selectedBreath.intensity ?? 1}
              onPointerDown={props.beginTransaction}
              onPointerUp={props.endTransaction}
              onChange={event => updateSelectedBreath(breath => { breath.intensity = Number(event.target.value) })}
            />
            <span className="breath-value">{Math.round((selectedBreath.intensity ?? 1) * 100)}%</span>
            <select value={selectedBreath.timbre || 'natural'} onChange={event => setSelectedTimbre(event.target.value as BreathTimbre)}>
              <option value="soft">Soft</option>
              <option value="natural">Natural</option>
              <option value="strong">Strong</option>
            </select>
          </div>
        )}
      </div>
    </section>
  )
}
