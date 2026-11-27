import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Note, Project, TimelineState, Track } from '../types'
import { tickDurationSeconds } from '../tempo'

const KEY_WIDTH = 64
const RULER_HEIGHT = 30
const VELOCITY_HEIGHT = 54
const MIN_PITCH = 24
const MAX_PITCH = 96

type Tool = 'select' | 'pencil' | 'erase' | 'pitch'

interface ViewState {
  rowHeight: number
  topPitch: number
}

interface NoteSnapshot {
  start: number
  duration: number
  pitch: number
}

interface DragState {
  mode: 'move' | 'resize' | 'create' | 'marquee' | 'velocity' | null
  noteId?: string
  startX: number
  startY: number
  originalStart: number
  originalDuration: number
  originalPitch: number
  originals: Record<string, NoteSnapshot>
}

interface Props {
  project: Project
  track: Track | undefined
  playheadTicks: number
  onSeek(ticks: number): void
  beginTransaction(): void
  endTransaction(): void
  updateProject(mutator: (project: Project) => void, transient?: boolean): void
  timeline: TimelineState
  onTimelineChange(timeline: TimelineState): void
}

function snap(ticks: number, step: number) {
  return Math.max(0, Math.round(ticks / step) * step)
}

function snapDelta(ticks: number, step: number) {
  return Math.round(ticks / step) * step
}

function blackKey(pitch: number) {
  return [1, 3, 6, 8, 10].includes(pitch % 12)
}

function noteName(pitch: number) {
  const names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
  return `${names[pitch % 12]}${Math.floor(pitch / 12) - 1}`
}

function cloneNote(note: Note): Note {
  return JSON.parse(JSON.stringify(note))
}

export default function PianoRoll(props: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const playheadCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const gradientCacheRef = useRef(new Map<string, CanvasGradient>())
  const wrapRef = useRef<HTMLDivElement | null>(null)
  const [tool, setTool] = useState<Tool>('pencil')
  const [gridDivision, setGridDivision] = useState(4)
  const [view, setView] = useState<ViewState>({ rowHeight: 15, topPitch: 79 })
  const [selectedNoteIds, setSelectedNoteIds] = useState<string[]>([])
  const [editing, setEditing] = useState<{ note: Note; x: number; y: number; value: string } | null>(null)
  const [marquee, setMarquee] = useState<{ x1: number; y1: number; x2: number; y2: number } | null>(null)
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null)
  const [vibratoEditor, setVibratoEditor] = useState<{ noteId: string; x: number; y: number } | null>(null)
  const [phonemeEditor, setPhonemeEditor] = useState<{ noteId: string; x: number; y: number; value: string; error?: string } | null>(null)
  const dragRef = useRef<DragState | null>(null)
  const pitchDragRef = useRef<{ noteId: string; pointIndex: number } | null>(null)
  const clipboardRef = useRef<Note[]>([])
  const [clipboardCount, setClipboardCount] = useState(0)
  const [pitchReadout, setPitchReadout] = useState<string | null>(null)
  const ppq = props.project.ppq
  const selectedSet = new Set(selectedNoteIds)

  const xForTick = useCallback((ticks: number) => KEY_WIDTH + ((ticks - props.timeline.scrollTicks) / ppq) * props.timeline.pxPerBeat, [props.timeline.scrollTicks, props.timeline.pxPerBeat, ppq])
  const tickForX = useCallback((x: number) => Math.max(0, props.timeline.scrollTicks + ((x - KEY_WIDTH) / props.timeline.pxPerBeat) * ppq), [props.timeline.scrollTicks, props.timeline.pxPerBeat, ppq])
  const yForPitch = useCallback((pitch: number) => RULER_HEIGHT + (view.topPitch - pitch) * view.rowHeight, [view])
  const pitchForY = useCallback((y: number) => Math.round(view.topPitch - (y - RULER_HEIGHT) / view.rowHeight), [view])

  const laneTop = useCallback(() => {
    const rect = canvasRef.current?.getBoundingClientRect()
    return Math.max(RULER_HEIGHT + 20, (rect?.height || 360) - VELOCITY_HEIGHT)
  }, [])

  const noteRect = useCallback((note: Note) => {
    const x = xForTick(note.start_ticks)
    const w = Math.max(5, (note.duration_ticks / ppq) * props.timeline.pxPerBeat)
    const y = yForPitch(note.pitch)
    return { x, y, w, h: view.rowHeight }
  }, [xForTick, yForPitch, ppq, props.timeline.pxPerBeat, view.rowHeight])

  const hitNote = useCallback((x: number, y: number) => {
    if (!props.track || y >= laneTop()) return null
    for (let i = props.track.notes.length - 1; i >= 0; i--) {
      const note = props.track.notes[i]
      const rect = noteRect(note)
      if (x >= rect.x && x <= rect.x + rect.w && y >= rect.y && y <= rect.y + rect.h) return note
    }
    return null
  }, [props.track, noteRect, laneTop])

  const hitVelocityNote = useCallback((x: number, y: number) => {
    if (!props.track || y < laneTop()) return null
    for (let i = props.track.notes.length - 1; i >= 0; i--) {
      const note = props.track.notes[i]
      const rect = noteRect(note)
      if (x >= rect.x && x <= rect.x + rect.w) return note
    }
    return null
  }, [props.track, noteRect, laneTop])

  useEffect(() => {
    const canvas = canvasRef.current
    const wrap = wrapRef.current
    if (!canvas || !wrap) return
    const draw = () => {
      const rect = wrap.getBoundingClientRect()
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
      const width = canvas.width / dpr
      const height = canvas.height / dpr
      const velocityTop = Math.max(RULER_HEIGHT + 20, height - VELOCITY_HEIGHT)
      ctx.clearRect(0, 0, width, height)
      ctx.fillStyle = '#101119'
      ctx.fillRect(0, 0, width, height)

      for (let pitch = MIN_PITCH; pitch <= MAX_PITCH; pitch++) {
        const y = yForPitch(pitch)
        if (y < RULER_HEIGHT - view.rowHeight || y > velocityTop) continue
        ctx.fillStyle = blackKey(pitch) ? '#131522' : '#181b29'
        ctx.fillRect(KEY_WIDTH, y, width - KEY_WIDTH, view.rowHeight)
        ctx.strokeStyle = pitch % 12 === 0 ? '#363b55' : '#242839'
        ctx.beginPath()
        ctx.moveTo(KEY_WIDTH, y)
        ctx.lineTo(width, y)
        ctx.stroke()
        ctx.fillStyle = blackKey(pitch) ? '#747b98' : '#b6bed8'
        ctx.font = '10px Inter, sans-serif'
        ctx.fillText(noteName(pitch), 8, y + view.rowHeight * 0.72)
        ctx.fillStyle = blackKey(pitch) ? '#1a1c27' : '#f2f4fb'
        ctx.fillRect(32, y, 30, view.rowHeight)
      }

      const beatTicks = ppq
      const barTicks = ppq * props.project.time_signature.numerator
      const startTick = Math.floor(props.timeline.scrollTicks / (ppq / 4)) * (ppq / 4)
      const endTick = props.timeline.scrollTicks + ((width - KEY_WIDTH) / props.timeline.pxPerBeat) * ppq + ppq
      for (let tick = startTick; tick <= endTick; tick += ppq / 4) {
        const x = xForTick(tick)
        const isBar = tick % barTicks === 0
        const isBeat = tick % beatTicks === 0
        ctx.strokeStyle = isBar ? '#59617f' : isBeat ? '#353b54' : '#232738'
        ctx.lineWidth = isBar ? 1.4 : 1
        ctx.beginPath()
        ctx.moveTo(x, RULER_HEIGHT)
        ctx.lineTo(x, velocityTop)
        ctx.stroke()
        if (isBar) {
          ctx.fillStyle = '#9aa5c5'
          ctx.font = '11px Inter, sans-serif'
          ctx.fillText(String(Math.floor(tick / barTicks) + 1), x + 5, 18)
        }
      }
      ctx.fillStyle = '#161927'
      ctx.fillRect(0, 0, width, RULER_HEIGHT)
      ctx.strokeStyle = '#3c425c'
      ctx.beginPath()
      ctx.moveTo(0, RULER_HEIGHT - 0.5)
      ctx.lineTo(width, RULER_HEIGHT - 0.5)
      ctx.stroke()
      for (let tick = startTick; tick <= endTick; tick += barTicks) {
        const x = xForTick(tick)
        ctx.fillStyle = '#aeb7d4'
        ctx.font = '11px Inter, sans-serif'
        ctx.fillText(String(Math.floor(tick / barTicks) + 1), x + 5, 19)
      }

      ctx.fillStyle = '#0c0f18'
      ctx.fillRect(0, velocityTop, width, VELOCITY_HEIGHT)
      ctx.fillStyle = '#111626'
      ctx.fillRect(KEY_WIDTH, velocityTop, width - KEY_WIDTH, VELOCITY_HEIGHT)
      ctx.strokeStyle = '#3a4159'
      ctx.beginPath()
      ctx.moveTo(0, velocityTop + 0.5)
      ctx.lineTo(width, velocityTop + 0.5)
      ctx.stroke()
      ctx.fillStyle = '#7883a4'
      ctx.font = '9px Inter, sans-serif'
      ctx.fillText('VEL', 22, velocityTop + 15)

      if (props.track) {
        let visibleNoteCount = 0
        for (const note of props.track.notes) {
          const x = xForTick(note.start_ticks)
          const w = Math.max(5, (note.duration_ticks / ppq) * props.timeline.pxPerBeat)
          const y = yForPitch(note.pitch)
          if (!(x + w < KEY_WIDTH || x > width || y > velocityTop || y + view.rowHeight < RULER_HEIGHT)) visibleNoteCount++
        }
        const drawDenseLabels = visibleNoteCount <= 220
        for (const note of props.track.notes) {
          const x = xForTick(note.start_ticks)
          const w = Math.max(5, (note.duration_ticks / ppq) * props.timeline.pxPerBeat)
          const y = yForPitch(note.pitch)
          if (x + w < KEY_WIDTH || x > width || y > velocityTop || y + view.rowHeight < RULER_HEIGHT) continue
          const selected = selectedSet.has(note.id)
          const denseView = visibleNoteCount > 220
          if (denseView) {
            ctx.fillStyle = selected ? '#9d8cff' : props.track.color
          } else {
            const gradientKey = `${note.pitch}:${view.rowHeight}:${selected ? 1 : 0}:${props.track.color}`
            let grad = gradientCacheRef.current.get(gradientKey)
            if (!grad) {
              grad = ctx.createLinearGradient(x, y, x, y + view.rowHeight)
              grad.addColorStop(0, selected ? '#b5a8ff' : props.track.color)
              grad.addColorStop(1, selected ? '#684fff' : '#342e78')
              gradientCacheRef.current.set(gradientKey, grad)
            }
            ctx.fillStyle = grad
          }
          ctx.beginPath()
          ctx.roundRect(x + 0.5, y + 1, w - 1, Math.max(4, view.rowHeight - 2), denseView ? 1 : 3)
          ctx.fill()
          if (!denseView || selected) {
            ctx.strokeStyle = selected ? '#ffffff' : '#786cff'
            ctx.lineWidth = selected ? 1.5 : 0.8
            ctx.stroke()
          }
          if (selected) {
            ctx.fillStyle = '#ffffff'
            ctx.fillRect(x + w - 3, y + 2, 2, view.rowHeight - 4)
          }
          if (note.vibrato && w > 34) {
            const startX = x + Math.max(0, Math.min(0.95, note.vibrato.start_ratio)) * w
            const seconds = tickDurationSeconds(props.project, note.start_ticks, note.duration_ticks)
            const amplitude = Math.max(1.2, Math.min(view.rowHeight * 0.24, note.vibrato.depth_cents / 100 * view.rowHeight * 0.28))
            ctx.strokeStyle = selected ? '#fff7a8' : '#ffd76dcc'
            ctx.lineWidth = 1
            ctx.beginPath()
            for (let sx = startX; sx <= x + w - 3; sx += 3) {
              const elapsed = ((sx - x) / Math.max(1, w)) * seconds
              const phase = 2 * Math.PI * note.vibrato.frequency_hz * elapsed + note.vibrato.phase
              const sy = y + view.rowHeight * 0.67 + Math.sin(phase) * amplitude
              if (sx === startX) ctx.moveTo(sx, sy); else ctx.lineTo(sx, sy)
            }
            ctx.stroke()
          }
          if (drawDenseLabels && w > 24) {
            ctx.fillStyle = '#f7f8ff'
            ctx.font = `${Math.min(12, Math.max(9, view.rowHeight - 3))}px Inter, sans-serif`
            if (note.lyric) ctx.fillText(note.lyric, x + 5, y + view.rowHeight * 0.68)
          }
          if (drawDenseLabels && note.phonemes?.length && w > 48 && view.rowHeight >= 13) {
            ctx.fillStyle = '#9cc8ff'
            ctx.font = '9px Inter, sans-serif'
            ctx.fillText(note.phonemes.map(p => p.symbol).join(' '), x + 5, y + view.rowHeight + 9)
          }

          if (note.pitch_curve.length) {
            const durationMs = Math.max(1, noteDurationMs(note))
            const ordered = [...note.pitch_curve].sort((a, b) => a.offset_ms - b.offset_ms)
            const linePoints = [
              { offset_ms: 0, cents: ordered[0].cents },
              ...ordered,
              { offset_ms: durationMs, cents: ordered[ordered.length - 1].cents },
            ]
            ctx.strokeStyle = selected ? '#b8ffdfff' : '#68dfb5cc'
            ctx.lineWidth = selected ? 1.6 : 1.1
            ctx.beginPath()
            linePoints.forEach((point, index) => {
              const pos = pitchPointPosition(note, point)
              if (index === 0) ctx.moveTo(pos.x, pos.y); else ctx.lineTo(pos.x, pos.y)
            })
            ctx.stroke()
            for (const point of ordered) {
              const pos = pitchPointPosition(note, point)
              ctx.fillStyle = selected ? '#effff8' : '#68dfb5'
              ctx.beginPath()
              ctx.arc(pos.x, pos.y, selected ? 3.2 : 2.6, 0, Math.PI * 2)
              ctx.fill()
            }
          }

          const laneBottom = height - 5
          const maxBar = VELOCITY_HEIGHT - 15
          const barHeight = Math.max(2, (note.velocity / 127) * maxBar)
          const bx = x + 2
          const bw = Math.max(2, w - 4)
          ctx.fillStyle = selected ? '#ffcc66' : '#6f7cff88'
          ctx.fillRect(bx, laneBottom - barHeight, bw, barHeight)
          if (selected && w > 20) {
            ctx.fillStyle = '#ffe0a0'
            ctx.font = '8px Inter, sans-serif'
            ctx.fillText(String(note.velocity), bx + 2, laneBottom - barHeight - 2)
          }
        }
      }

      if (marquee) {
        const x = Math.min(marquee.x1, marquee.x2)
        const y = Math.min(marquee.y1, marquee.y2)
        const w = Math.abs(marquee.x2 - marquee.x1)
        const h = Math.abs(marquee.y2 - marquee.y1)
        ctx.fillStyle = '#6f8dff22'
        ctx.fillRect(x, y, w, h)
        ctx.strokeStyle = '#91a8ff'
        ctx.setLineDash([4, 3])
        ctx.strokeRect(x, y, w, h)
        ctx.setLineDash([])
      }

      ctx.restore()
    }
    draw()
    const observer = new ResizeObserver(draw)
    observer.observe(wrap)
    return () => observer.disconnect()
  }, [props.project, props.track, props.timeline, view, selectedNoteIds, marquee, xForTick, yForPitch, ppq])

  useEffect(() => {
    const canvas = playheadCanvasRef.current
    const wrap = wrapRef.current
    if (!canvas || !wrap) return
    const draw = () => {
      const rect = wrap.getBoundingClientRect()
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
      const width = canvas.width / dpr
      const height = canvas.height / dpr
      ctx.clearRect(0, 0, width, height)
      const px = xForTick(props.playheadTicks)
      if (px >= KEY_WIDTH && px <= width) {
        ctx.strokeStyle = '#ff4f78'
        ctx.lineWidth = 1.5
        ctx.beginPath()
        ctx.moveTo(px, 0)
        ctx.lineTo(px, height)
        ctx.stroke()
        ctx.fillStyle = '#ff4f78'
        ctx.beginPath()
        ctx.moveTo(px - 6, 0)
        ctx.lineTo(px + 6, 0)
        ctx.lineTo(px, 9)
        ctx.closePath()
        ctx.fill()
      }
      ctx.restore()
    }
    draw()
    const observer = new ResizeObserver(draw)
    observer.observe(wrap)
    return () => observer.disconnect()
  }, [props.playheadTicks, xForTick])

  function mutateTrack(mutator: (track: Track) => void, transient = true) {
    if (!props.track) return
    const trackId = props.track.id
    props.updateProject(project => {
      const track = project.tracks.find(t => t.id === trackId)
      if (track) mutator(track)
    }, transient)
  }

  function pointerPos(event: React.PointerEvent | React.MouseEvent) {
    const rect = canvasRef.current!.getBoundingClientRect()
    return { x: event.clientX - rect.left, y: event.clientY - rect.top }
  }

  function snapshotsFor(ids: string[]): Record<string, NoteSnapshot> {
    const result: Record<string, NoteSnapshot> = {}
    for (const note of props.track?.notes || []) {
      if (ids.includes(note.id)) result[note.id] = { start: note.start_ticks, duration: note.duration_ticks, pitch: note.pitch }
    }
    return result
  }

  function selectOnly(noteId: string) {
    setSelectedNoteIds([noteId])
  }

  function velocityFromY(y: number) {
    const top = laneTop() + 5
    const bottom = laneTop() + VELOCITY_HEIGHT - 7
    return Math.max(1, Math.min(127, Math.round(((bottom - y) / Math.max(1, bottom - top)) * 127)))
  }

  function noteDurationMs(note: Note) {
    return tickDurationSeconds(props.project, note.start_ticks, note.duration_ticks) * 1000
  }

  function pitchPointPosition(note: Note, point: { offset_ms: number; cents: number }) {
    const rect = noteRect(note)
    const durationMs = Math.max(1, noteDurationMs(note))
    const x = rect.x + 2 + Math.max(0, Math.min(1, point.offset_ms / durationMs)) * Math.max(1, rect.w - 4)
    const center = rect.y + rect.h / 2
    const half = Math.max(3, rect.h / 2 - 2)
    const y = center - Math.max(-120, Math.min(120, point.cents)) / 100 * half
    return { x, y }
  }

  function pitchPointAt(note: Note, x: number, y: number) {
    const rect = noteRect(note)
    const durationMs = Math.max(1, noteDurationMs(note))
    const ratio = Math.max(0, Math.min(1, (x - rect.x - 2) / Math.max(1, rect.w - 4)))
    const center = rect.y + rect.h / 2
    const half = Math.max(3, rect.h / 2 - 2)
    const cents = Math.max(-120, Math.min(120, ((center - y) / half) * 100))
    return { offset_ms: Math.round(ratio * durationMs), cents: Math.round(cents) }
  }

  function hitPitchPoint(x: number, y: number) {
    if (!props.track || y >= laneTop()) return null
    let best: { note: Note; pointIndex: number; distance: number } | null = null
    for (const note of props.track.notes) {
      note.pitch_curve.forEach((point, pointIndex) => {
        const pos = pitchPointPosition(note, point)
        const distance = Math.hypot(pos.x - x, pos.y - y)
        if (distance < 9 && (!best || distance < best.distance)) best = { note, pointIndex, distance }
      })
    }
    return best
  }

  function onPointerDown(event: React.PointerEvent) {
    if (!props.track || event.button === 2) return
    setMenu(null)
    const { x, y } = pointerPos(event)
    canvasRef.current?.setPointerCapture(event.pointerId)
    if (y < RULER_HEIGHT) {
      props.onSeek(snap(tickForX(x), ppq / 4))
      return
    }
    if (x < KEY_WIDTH) return

    if (y >= laneTop()) {
      const hit = hitVelocityNote(x, y)
      if (hit) {
        if (!selectedSet.has(hit.id)) selectOnly(hit.id)
        props.beginTransaction()
        dragRef.current = {
          mode: 'velocity', noteId: hit.id, startX: x, startY: y,
          originalStart: hit.start_ticks, originalDuration: hit.duration_ticks, originalPitch: hit.pitch,
          originals: snapshotsFor([hit.id]),
        }
        mutateTrack(track => {
          const note = track.notes.find(n => n.id === hit.id)
          if (note) note.velocity = velocityFromY(y)
        }, true)
      }
      return
    }

    if (tool === 'pitch') {
      const hitPoint = hitPitchPoint(x, y)
      if (hitPoint && event.altKey) {
        props.beginTransaction()
        mutateTrack(track => {
          const note = track.notes.find(item => item.id === hitPoint.note.id)
          if (note) note.pitch_curve.splice(hitPoint.pointIndex, 1)
        }, true)
        props.endTransaction()
        return
      }
      if (hitPoint) {
        selectOnly(hitPoint.note.id)
        props.beginTransaction()
        pitchDragRef.current = { noteId: hitPoint.note.id, pointIndex: hitPoint.pointIndex }
        return
      }
      const hit = hitNote(x, y)
      if (hit) {
        selectOnly(hit.id)
        const point = pitchPointAt(hit, x, y)
        props.beginTransaction()
        let pointIndex = 0
        mutateTrack(track => {
          const note = track.notes.find(item => item.id === hit.id)
          if (note) {
            note.pitch_curve.push(point)
            pointIndex = note.pitch_curve.length - 1
          }
        }, true)
        pitchDragRef.current = { noteId: hit.id, pointIndex }
      }
      return
    }

    const hit = hitNote(x, y)
    if (tool === 'erase') {
      if (hit) {
        props.beginTransaction()
        mutateTrack(track => { track.notes = track.notes.filter(n => !selectedSet.has(n.id) && n.id !== hit.id) }, true)
        setSelectedNoteIds([])
        props.endTransaction()
      }
      return
    }

    if (tool === 'pencil' && !hit) {
      props.beginTransaction()
      const step = ppq / gridDivision
      const start = snap(tickForX(x), step)
      const pitch = Math.max(MIN_PITCH, Math.min(MAX_PITCH, pitchForY(y)))
      const id = `note_${crypto.randomUUID().slice(0, 12)}`
      const duration = step
      mutateTrack(track => {
        track.notes.push({
          id,
          start_ticks: start,
          duration_ticks: duration,
          pitch,
          lyric: '',
          velocity: 90,
          phonemes: [],
          pitch_curve: [],
          vibrato: null,
          techniques: [],
        })
        track.notes.sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch)
      }, true)
      selectOnly(id)
      dragRef.current = {
        mode: 'resize', noteId: id, startX: x, startY: y,
        originalStart: start, originalDuration: duration, originalPitch: pitch,
        originals: { [id]: { start, duration, pitch } },
      }
      return
    }

    if (hit) {
      let nextSelection = selectedNoteIds
      if (event.shiftKey) {
        nextSelection = selectedSet.has(hit.id) ? selectedNoteIds.filter(id => id !== hit.id) : [...selectedNoteIds, hit.id]
        setSelectedNoteIds(nextSelection)
        if (selectedSet.has(hit.id)) return
      } else if (!selectedSet.has(hit.id)) {
        nextSelection = [hit.id]
        setSelectedNoteIds(nextSelection)
      }
      const nx = xForTick(hit.start_ticks)
      const nw = Math.max(5, (hit.duration_ticks / ppq) * props.timeline.pxPerBeat)
      const resize = x > nx + nw - 7
      props.beginTransaction()
      dragRef.current = {
        mode: resize ? 'resize' : 'move',
        noteId: hit.id,
        startX: x,
        startY: y,
        originalStart: hit.start_ticks,
        originalDuration: hit.duration_ticks,
        originalPitch: hit.pitch,
        originals: snapshotsFor(nextSelection.length ? nextSelection : [hit.id]),
      }
    } else if (tool === 'select') {
      if (!event.shiftKey) setSelectedNoteIds([])
      dragRef.current = {
        mode: 'marquee', startX: x, startY: y, originalStart: 0, originalDuration: 0, originalPitch: 0, originals: {},
      }
      setMarquee({ x1: x, y1: y, x2: x, y2: y })
    }
  }

  function onPointerMove(event: React.PointerEvent) {
    const drag = dragRef.current
    if (!props.track) return
    const { x, y } = pointerPos(event)
    const step = ppq / gridDivision

    const pitchDrag = pitchDragRef.current
    if (pitchDrag) {
      const sourceNote = props.track.notes.find(item => item.id === pitchDrag.noteId)
      if (sourceNote) {
        const point = pitchPointAt(sourceNote, x, y)
        setPitchReadout(`${point.offset_ms} ms · ${point.cents > 0 ? '+' : ''}${point.cents}¢`)
      }
      mutateTrack(track => {
        const note = track.notes.find(item => item.id === pitchDrag.noteId)
        if (note?.pitch_curve[pitchDrag.pointIndex]) {
          note.pitch_curve[pitchDrag.pointIndex] = pitchPointAt(note, x, y)
        }
      }, true)
      return
    }

    if (!drag) return
    if (drag.mode === 'marquee') {
      setMarquee(current => current ? { ...current, x2: x, y2: y } : current)
      const x1 = Math.min(drag.startX, x), x2 = Math.max(drag.startX, x)
      const y1 = Math.min(drag.startY, y), y2 = Math.max(drag.startY, y)
      const hits = props.track.notes.filter(note => {
        const rect = noteRect(note)
        return rect.x < x2 && rect.x + rect.w > x1 && rect.y < y2 && rect.y + rect.h > y1
      }).map(note => note.id)
      setSelectedNoteIds(event.shiftKey ? Array.from(new Set([...selectedNoteIds, ...hits])) : hits)
      return
    }

    if (drag.mode === 'velocity' && drag.noteId) {
      const velocity = velocityFromY(y)
      mutateTrack(track => {
        const note = track.notes.find(n => n.id === drag.noteId)
        if (note) note.velocity = velocity
      }, true)
      return
    }

    const deltaTicks = snapDelta(Math.round(((x - drag.startX) / props.timeline.pxPerBeat) * ppq), step)
    const deltaPitch = Math.round((drag.startY - y) / view.rowHeight)
    mutateTrack(track => {
      const originals = drag.originals
      const ids = Object.keys(originals)
      if (!ids.length) return
      if (drag.mode === 'resize') {
        const maxShrink = Math.min(...ids.map(id => originals[id].duration - step))
        const allowedDelta = Math.max(deltaTicks, -maxShrink)
        for (const id of ids) {
          const note = track.notes.find(n => n.id === id)
          if (note) note.duration_ticks = Math.max(step, originals[id].duration + allowedDelta)
        }
      } else if (drag.mode === 'move') {
        const minStart = Math.min(...ids.map(id => originals[id].start))
        const allowedTickDelta = Math.max(deltaTicks, -minStart)
        const minPitch = Math.min(...ids.map(id => originals[id].pitch))
        const maxPitch = Math.max(...ids.map(id => originals[id].pitch))
        const allowedPitchDelta = Math.max(MIN_PITCH - minPitch, Math.min(MAX_PITCH - maxPitch, deltaPitch))
        for (const id of ids) {
          const note = track.notes.find(n => n.id === id)
          if (note) {
            note.start_ticks = originals[id].start + allowedTickDelta
            note.pitch = originals[id].pitch + allowedPitchDelta
          }
        }
      }
      track.notes.sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch)
    }, true)
  }

  function onPointerUp(event: React.PointerEvent) {
    const pitchDrag = pitchDragRef.current
    if (pitchDrag) {
      mutateTrack(track => {
        const note = track.notes.find(item => item.id === pitchDrag.noteId)
        if (note) note.pitch_curve.sort((a, b) => a.offset_ms - b.offset_ms)
      }, true)
      props.endTransaction()
      pitchDragRef.current = null
      window.setTimeout(() => setPitchReadout(null), 1600)
    }
    const hadDrag = dragRef.current
    if (hadDrag && hadDrag.mode !== 'marquee') props.endTransaction()
    dragRef.current = null
    setMarquee(null)
    canvasRef.current?.releasePointerCapture(event.pointerId)
  }

  function onDoubleClick(event: React.MouseEvent) {
    if (!props.track) return
    const { x, y } = pointerPos(event)
    const hit = hitNote(x, y)
    if (hit) setEditing({ note: hit, x, y, value: hit.lyric })
  }

  function commitLyric() {
    if (!editing) return
    const value = editing.value.trim()
    const noteId = editing.note.id
    props.beginTransaction()
    mutateTrack(track => {
      const note = track.notes.find(n => n.id === noteId)
      if (note) {
        note.lyric = value
        note.phonemes = []
      }
    }, true)
    props.endTransaction()
    setEditing(null)
  }

  function selectedNotes(): Note[] {
    if (!props.track) return []
    return props.track.notes.filter(note => selectedSet.has(note.id)).sort((a, b) => a.start_ticks - b.start_ticks)
  }

  function copySelection() {
    clipboardRef.current = selectedNotes().map(cloneNote)
    setClipboardCount(clipboardRef.current.length)
  }

  function pasteClipboard(targetStart?: number) {
    const clipboard = clipboardRef.current
    if (!clipboard.length || !props.track) return
    props.beginTransaction()
    const step = ppq / gridDivision
    const minStart = Math.min(...clipboard.map(note => note.start_ticks))
    const anchor = targetStart ?? snap(props.playheadTicks, step)
    const delta = Math.max(anchor - minStart, -minStart)
    const newIds: string[] = []
    mutateTrack(track => {
      for (const source of clipboard) {
        const note = cloneNote(source)
        note.id = `note_${crypto.randomUUID().slice(0, 12)}`
        note.start_ticks = source.start_ticks + delta
        newIds.push(note.id)
        track.notes.push(note)
      }
      track.notes.sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch)
    }, true)
    setSelectedNoteIds(newIds)
    props.endTransaction()
  }

  function duplicateSelection() {
    const notes = selectedNotes()
    if (!notes.length) return
    clipboardRef.current = notes.map(cloneNote)
    setClipboardCount(clipboardRef.current.length)
    const end = Math.max(...notes.map(note => note.start_ticks + note.duration_ticks))
    pasteClipboard(end)
  }

  function deleteSelection() {
    if (!selectedNoteIds.length) return
    props.beginTransaction()
    mutateTrack(track => { track.notes = track.notes.filter(note => !selectedSet.has(note.id)) }, true)
    setSelectedNoteIds([])
    props.endTransaction()
  }

  function quantizeSelection() {
    if (!props.track) return
    const ids = selectedNoteIds.length ? selectedNoteIds : props.track.notes.map(note => note.id)
    const step = ppq / gridDivision
    props.beginTransaction()
    mutateTrack(track => {
      for (const note of track.notes) {
        if (!ids.includes(note.id)) continue
        note.start_ticks = snap(note.start_ticks, step)
        note.duration_ticks = Math.max(step, snap(note.duration_ticks, step))
      }
      track.notes.sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch)
    }, true)
    props.endTransaction()
  }

  function onWheel(event: React.WheelEvent) {
    if (event.ctrlKey || event.metaKey) {
      const factor = event.deltaY > 0 ? 0.9 : 1.1
      props.onTimelineChange({ ...props.timeline, pxPerBeat: Math.max(32, Math.min(360, props.timeline.pxPerBeat * factor)) })
    } else if (event.altKey) {
      const factor = event.deltaY > 0 ? 0.9 : 1.1
      setView(v => ({ ...v, rowHeight: Math.max(8, Math.min(28, v.rowHeight * factor)) }))
    } else if (event.shiftKey) {
      setView(v => ({ ...v, topPitch: Math.max(58, Math.min(MAX_PITCH, v.topPitch + (event.deltaY > 0 ? -2 : 2))) }))
    } else {
      props.onTimelineChange({ ...props.timeline, scrollTicks: Math.max(0, props.timeline.scrollTicks + event.deltaY * 2 + event.deltaX * 2) })
    }
  }


  function openVibratoEditor(x = 90, y = 80) {
    if (selectedNoteIds.length !== 1) return
    const rect = wrapRef.current?.getBoundingClientRect()
    const width = rect?.width || 900
    const height = rect?.height || 420
    const editorWidth = 228
    const editorHeight = 265
    props.beginTransaction()
    setVibratoEditor({
      noteId: selectedNoteIds[0],
      x: Math.max(8, Math.min(x, width - editorWidth - 8)),
      y: Math.max(34, Math.min(y, height - editorHeight - 8)),
    })
    setMenu(null)
  }

  function closeVibratoEditor() {
    setVibratoEditor(null)
    props.endTransaction()
  }

  function updateVibrato(noteId: string, patch: Partial<NonNullable<Note['vibrato']>> | null) {
    mutateTrack(track => {
      const note = track.notes.find(item => item.id === noteId)
      if (!note) return
      if (patch === null) {
        note.vibrato = null
      } else {
        note.vibrato = {
          start_ratio: 0.35,
          depth_cents: 35,
          frequency_hz: 5.2,
          phase: 0,
          ...(note.vibrato || {}),
          ...patch,
        }
      }
    }, true)
  }

  function openPhonemeEditor(x = 100, y = 92) {
    if (selectedNoteIds.length !== 1 || !props.track) return
    const note = props.track.notes.find(item => item.id === selectedNoteIds[0])
    if (!note) return
    setPhonemeEditor({
      noteId: note.id,
      x: Math.max(8, Math.min(x, (wrapRef.current?.clientWidth || 900) - 270)),
      y: Math.max(34, Math.min(y, (wrapRef.current?.clientHeight || 420) - 170)),
      value: note.phonemes.map(item => item.symbol).join(' '),
    })
    setMenu(null)
  }

  async function applyPhonemeOverride() {
    if (!phonemeEditor || !props.track) return
    const note = props.track.notes.find(item => item.id === phonemeEditor.noteId)
    if (!note) return
    const symbols = phonemeEditor.value.split(/\s+/).filter(Boolean)
    try {
      const durationMs = noteDurationMs(note)
      const timed = await api.timePhonemes(symbols, durationMs)
      props.updateProject(project => {
        const target = project.tracks.find(item => item.id === props.track?.id)?.notes.find(item => item.id === note.id)
        if (target) target.phonemes = timed
      }, false)
      setPhonemeEditor(null)
    } catch (error) {
      setPhonemeEditor(current => current ? { ...current, error: error instanceof Error ? error.message : String(error) } : current)
    }
  }

  function resetPhonemes() {
    if (!phonemeEditor || !props.track) return
    const noteId = phonemeEditor.noteId
    props.updateProject(project => {
      const target = project.tracks.find(item => item.id === props.track?.id)?.notes.find(item => item.id === noteId)
      if (target) target.phonemes = []
    }, false)
    setPhonemeEditor(null)
  }

  function handleEditorKey(event: KeyboardEvent) {
    if ((event.target as HTMLElement).tagName === 'INPUT') return
    const key = event.key.toLowerCase()
    if ((event.ctrlKey || event.metaKey) && key === 'a') {
      event.preventDefault()
      setSelectedNoteIds(props.track?.notes.map(note => note.id) || [])
      return
    }
    if ((event.ctrlKey || event.metaKey) && key === 'c') {
      event.preventDefault(); copySelection(); return
    }
    if ((event.ctrlKey || event.metaKey) && key === 'v') {
      event.preventDefault(); pasteClipboard(); return
    }
    if ((event.ctrlKey || event.metaKey) && key === 'd') {
      event.preventDefault(); duplicateSelection(); return
    }
    if (!event.ctrlKey && !event.metaKey && !event.altKey) {
      if (key === 'v') setTool('select')
      if (key === 'b') setTool('pencil')
      if (key === 'e') setTool('erase')
      if (key === 'p') setTool('pitch')
      if (key === 'q') quantizeSelection()
    }
    if ((event.key === 'Delete' || event.key === 'Backspace') && selectedNoteIds.length) deleteSelection()
  }

  useEffect(() => {
    function listener(event: KeyboardEvent) {
      handleEditorKey(event)
    }
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  })

  function onContextMenu(event: React.MouseEvent) {
    event.preventDefault()
    const { x, y } = pointerPos(event)
    const hit = hitNote(x, y)
    if (hit && !selectedSet.has(hit.id)) selectOnly(hit.id)
    setMenu({ x, y })
  }

  function menuAction(action: () => void) {
    action()
    setMenu(null)
  }

  return (
    <div className="piano-roll-shell">
      <div className="editor-toolbar">
        <div className="tool-group">
          <button className={tool === 'select' ? 'tool active' : 'tool'} onClick={() => setTool('select')} title="Select/move (V)">➤</button>
          <button className={tool === 'pencil' ? 'tool active' : 'tool'} onClick={() => setTool('pencil')} title="Note brush (B)">✎</button>
          <button className={tool === 'erase' ? 'tool active' : 'tool'} onClick={() => setTool('erase')} title="Eraser (E)">⌫</button>
          <button className={tool === 'pitch' ? 'tool active' : 'tool'} onClick={() => setTool('pitch')} title="Per-note pitch handles (P); Alt+click deletes a handle">∿ Pitch</button>
        </div>
        <label>Grid
          <select value={gridDivision} onChange={e => setGridDivision(Number(e.target.value))}>
            <option value={1}>1/4</option><option value={2}>1/8</option><option value={4}>1/16</option><option value={8}>1/32</option>
          </select>
        </label>
        <label>Zoom<input type="range" min="32" max="360" value={props.timeline.pxPerBeat} onChange={e => props.onTimelineChange({ ...props.timeline, pxPerBeat: Number(e.target.value) })} /></label>
        <label>Row<input type="range" min="8" max="28" value={view.rowHeight} onChange={e => setView(v => ({ ...v, rowHeight: Number(e.target.value) }))} /></label>
        <div className="tool-group edit-actions">
          <button className="tool" onClick={copySelection} disabled={!selectedNoteIds.length} title="Copy (Ctrl+C)">Copy</button>
          <button className="tool" onClick={() => pasteClipboard()} disabled={!clipboardCount} title="Paste at playhead (Ctrl+V)">Paste</button>
          <button className="tool" onClick={duplicateSelection} disabled={!selectedNoteIds.length} title="Duplicate (Ctrl+D)">Dup</button>
          <button className="tool" onClick={quantizeSelection} title="Quantize selection/all (Q)">Quant</button>
          <button className="tool" onClick={() => openVibratoEditor()} disabled={selectedNoteIds.length !== 1} title="Edit vibrato for selected note">Vibrato</button>
        </div>
        <div className="selection-count">{selectedNoteIds.length ? `${selectedNoteIds.length} selected` : ''}</div>
        <div className="pitch-readout">{pitchReadout || ''}</div>
        <div className="editor-hint">V/B/E/P · Ctrl+C/V/D</div>
      </div>
      <div className="piano-roll-wrap" ref={wrapRef} tabIndex={0}>
        <canvas
          ref={canvasRef}
          className="piano-roll-canvas"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onDoubleClick={onDoubleClick}
          onWheel={onWheel}
          onContextMenu={onContextMenu}
        />
        <canvas ref={playheadCanvasRef} className="piano-playhead-overlay" />
        {menu && (
          <div className="piano-context-menu" style={{ left: menu.x, top: menu.y }}>
            <button disabled={!selectedNoteIds.length} onClick={() => menuAction(copySelection)}>Copy</button>
            <button disabled={!clipboardCount} onClick={() => menuAction(() => pasteClipboard())}>Paste at playhead</button>
            <button disabled={!selectedNoteIds.length} onClick={() => menuAction(duplicateSelection)}>Duplicate</button>
            <button disabled={!selectedNoteIds.length} onClick={() => menuAction(quantizeSelection)}>Quantize</button>
            <button disabled={selectedNoteIds.length !== 1} onClick={() => openVibratoEditor(menu.x + 8, menu.y + 8)}>Vibrato…</button>
            <button disabled={selectedNoteIds.length !== 1} onClick={() => openPhonemeEditor(menu.x + 8, menu.y + 8)}>Phonemes…</button>
            <button disabled={!selectedNoteIds.length} className="danger" onClick={() => menuAction(deleteSelection)}>Delete</button>
          </div>
        )}
        {editing && (
          <input
            className="lyric-editor"
            style={{ left: editing.x + 2, top: editing.y + 2 }}
            autoFocus
            value={editing.value}
            onChange={e => setEditing({ ...editing, value: e.target.value })}
            onBlur={commitLyric}
            onKeyDown={e => { if (e.key === 'Enter') commitLyric(); if (e.key === 'Escape') setEditing(null) }}
          />
        )}
        {phonemeEditor && (
          <div className="phoneme-editor" style={{ left: phonemeEditor.x, top: phonemeEditor.y }}>
            <div className="vibrato-header"><strong>Manual phonemes</strong><button onClick={() => setPhonemeEditor(null)}>×</button></div>
            <input
              autoFocus
              value={phonemeEditor.value}
              placeholder="space-separated IPA/phoneme symbols"
              onChange={event => setPhonemeEditor({ ...phonemeEditor, value: event.target.value, error: undefined })}
              onKeyDown={event => { if (event.key === 'Enter') applyPhonemeOverride() }}
            />
            {phonemeEditor.error && <div className="phoneme-error">{phonemeEditor.error}</div>}
            <div className="phoneme-actions">
              <button onClick={applyPhonemeOverride}>Apply</button>
              <button onClick={resetPhonemes}>Reset auto</button>
            </div>
          </div>
        )}
        {vibratoEditor && props.track && (() => {
          const note = props.track.notes.find(item => item.id === vibratoEditor.noteId)
          if (!note) return null
          const vibrato = note.vibrato || { start_ratio: 0.35, depth_cents: 35, frequency_hz: 5.2, phase: 0 }
          return (
            <div className="vibrato-editor" style={{ left: vibratoEditor.x, top: vibratoEditor.y }}>
              <div className="vibrato-header">
                <strong>Vibrato</strong>
                <button onClick={closeVibratoEditor}>×</button>
              </div>
              <label className="vibrato-enable">
                <input type="checkbox" checked={!!note.vibrato} onChange={event => updateVibrato(note.id, event.target.checked ? {} : null)} />
                Enabled
              </label>
              <label>Start {(vibrato.start_ratio * 100).toFixed(0)}%
                <input type="range" min="0" max="0.85" step="0.01" value={vibrato.start_ratio} disabled={!note.vibrato} onChange={event => updateVibrato(note.id, { start_ratio: Number(event.target.value) })} />
              </label>
              <label>Depth {vibrato.depth_cents.toFixed(0)}¢
                <input type="range" min="0" max="120" step="1" value={vibrato.depth_cents} disabled={!note.vibrato} onChange={event => updateVibrato(note.id, { depth_cents: Number(event.target.value) })} />
              </label>
              <label>Rate {vibrato.frequency_hz.toFixed(1)}Hz
                <input type="range" min="2.5" max="8" step="0.1" value={vibrato.frequency_hz} disabled={!note.vibrato} onChange={event => updateVibrato(note.id, { frequency_hz: Number(event.target.value) })} />
              </label>
              <label>Phase {vibrato.phase.toFixed(2)}
                <input type="range" min="0" max={Math.PI * 2} step="0.01" value={vibrato.phase} disabled={!note.vibrato} onChange={event => updateVibrato(note.id, { phase: Number(event.target.value) })} />
              </label>
            </div>
          )
        })()}
      </div>
    </div>
  )
}
