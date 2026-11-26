import { useCallback, useEffect, useRef, useState } from 'react'
import type { Note, Project, TimelineState, Track } from '../types'

const KEY_WIDTH = 64
const RULER_HEIGHT = 30
const MIN_PITCH = 24
const MAX_PITCH = 96

type Tool = 'select' | 'pencil' | 'erase'

interface ViewState {
  rowHeight: number
  topPitch: number
}

interface DragState {
  mode: 'move' | 'resize' | 'create' | null
  noteId?: string
  startX: number
  startY: number
  originalStart: number
  originalDuration: number
  originalPitch: number
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

function blackKey(pitch: number) {
  return [1, 3, 6, 8, 10].includes(pitch % 12)
}

function noteName(pitch: number) {
  const names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
  return `${names[pitch % 12]}${Math.floor(pitch / 12) - 1}`
}

export default function PianoRoll(props: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const wrapRef = useRef<HTMLDivElement | null>(null)
  const [tool, setTool] = useState<Tool>('pencil')
  const [gridDivision, setGridDivision] = useState(4)
  const [view, setView] = useState<ViewState>({ rowHeight: 15, topPitch: 79 })
  const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null)
  const [editing, setEditing] = useState<{ note: Note; x: number; y: number; value: string } | null>(null)
  const dragRef = useRef<DragState | null>(null)
  const ppq = props.project.ppq

  const xForTick = useCallback((ticks: number, width = 1200) => KEY_WIDTH + ((ticks - props.timeline.scrollTicks) / ppq) * props.timeline.pxPerBeat, [view, ppq])
  const tickForX = useCallback((x: number) => Math.max(0, props.timeline.scrollTicks + ((x - KEY_WIDTH) / props.timeline.pxPerBeat) * ppq), [view, ppq])
  const yForPitch = useCallback((pitch: number) => RULER_HEIGHT + (view.topPitch - pitch) * view.rowHeight, [view])
  const pitchForY = useCallback((y: number) => Math.round(view.topPitch - (y - RULER_HEIGHT) / view.rowHeight), [view])

  const hitNote = useCallback((x: number, y: number) => {
    if (!props.track) return null
    for (let i = props.track.notes.length - 1; i >= 0; i--) {
      const note = props.track.notes[i]
      const nx = xForTick(note.start_ticks)
      const nw = Math.max(5, (note.duration_ticks / ppq) * props.timeline.pxPerBeat)
      const ny = yForPitch(note.pitch)
      if (x >= nx && x <= nx + nw && y >= ny && y <= ny + view.rowHeight) return note
    }
    return null
  }, [props.track, xForTick, yForPitch, ppq, view])

  useEffect(() => {
    const canvas = canvasRef.current
    const wrap = wrapRef.current
    if (!canvas || !wrap) return
    const resize = () => {
      const rect = wrap.getBoundingClientRect()
      const dpr = window.devicePixelRatio || 1
      canvas.width = Math.max(1, Math.floor(rect.width * dpr))
      canvas.height = Math.max(1, Math.floor(rect.height * dpr))
      canvas.style.width = `${rect.width}px`
      canvas.style.height = `${rect.height}px`
      draw()
    }
    const draw = () => {
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      const dpr = window.devicePixelRatio || 1
      ctx.save()
      ctx.scale(dpr, dpr)
      const width = canvas.width / dpr
      const height = canvas.height / dpr
      ctx.clearRect(0, 0, width, height)
      ctx.fillStyle = '#101119'
      ctx.fillRect(0, 0, width, height)

      // Pitch rows.
      for (let pitch = MIN_PITCH; pitch <= MAX_PITCH; pitch++) {
        const y = yForPitch(pitch)
        if (y < RULER_HEIGHT - view.rowHeight || y > height) continue
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

      // Time grid.
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
        ctx.lineTo(x, height)
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

      // Notes.
      if (props.track) {
        for (const note of props.track.notes) {
          const x = xForTick(note.start_ticks)
          const w = Math.max(5, (note.duration_ticks / ppq) * props.timeline.pxPerBeat)
          const y = yForPitch(note.pitch)
          if (x + w < KEY_WIDTH || x > width || y > height || y + view.rowHeight < RULER_HEIGHT) continue
          const selected = note.id === selectedNoteId
          const grad = ctx.createLinearGradient(x, y, x, y + view.rowHeight)
          grad.addColorStop(0, selected ? '#9f8cff' : props.track.color)
          grad.addColorStop(1, selected ? '#5d48c8' : '#342e78')
          ctx.fillStyle = grad
          ctx.beginPath()
          ctx.roundRect(x + 0.5, y + 1, w - 1, Math.max(4, view.rowHeight - 2), 3)
          ctx.fill()
          ctx.strokeStyle = selected ? '#ffffff' : '#786cff'
          ctx.lineWidth = selected ? 1.4 : 0.8
          ctx.stroke()
          if (w > 24) {
            ctx.fillStyle = '#f7f8ff'
            ctx.font = `${Math.min(12, Math.max(9, view.rowHeight - 3))}px Inter, sans-serif`
            ctx.fillText(note.lyric || '—', x + 5, y + view.rowHeight * 0.68)
          }
          if (note.phonemes?.length && w > 48 && view.rowHeight >= 13) {
            ctx.fillStyle = '#9cc8ff'
            ctx.font = '9px Inter, sans-serif'
            ctx.fillText(note.phonemes.map(p => p.symbol).join(' '), x + 5, y + view.rowHeight + 9)
          }
        }
      }

      // Playhead.
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
    resize()
    const observer = new ResizeObserver(resize)
    observer.observe(wrap)
    return () => observer.disconnect()
  }, [props.project, props.track, props.playheadTicks, view, selectedNoteId, xForTick, yForPitch, ppq])

  function mutateTrack(mutator: (track: Track) => void, transient = true) {
    if (!props.track) return
    const trackId = props.track.id
    props.updateProject(project => {
      const track = project.tracks.find(t => t.id === trackId)
      if (track) mutator(track)
    }, transient)
  }

  function pointerPos(event: React.PointerEvent) {
    const rect = canvasRef.current!.getBoundingClientRect()
    return { x: event.clientX - rect.left, y: event.clientY - rect.top }
  }

  function onPointerDown(event: React.PointerEvent) {
    if (!props.track || event.button === 2) return
    const { x, y } = pointerPos(event)
    canvasRef.current?.setPointerCapture(event.pointerId)
    if (y < RULER_HEIGHT) {
      props.onSeek(snap(tickForX(x), ppq / 4))
      return
    }
    if (x < KEY_WIDTH) return
    const hit = hitNote(x, y)
    props.beginTransaction()
    if (tool === 'erase') {
      if (hit) mutateTrack(track => { track.notes = track.notes.filter(n => n.id !== hit.id) }, true)
      props.endTransaction()
      return
    }
    if (tool === 'pencil' && !hit) {
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
      setSelectedNoteId(id)
      dragRef.current = { mode: 'resize', noteId: id, startX: x, startY: y, originalStart: start, originalDuration: duration, originalPitch: pitch }
      return
    }
    if (hit) {
      setSelectedNoteId(hit.id)
      const nx = xForTick(hit.start_ticks)
      const nw = Math.max(5, (hit.duration_ticks / ppq) * props.timeline.pxPerBeat)
      const resize = x > nx + nw - 7
      dragRef.current = {
        mode: resize ? 'resize' : 'move',
        noteId: hit.id,
        startX: x,
        startY: y,
        originalStart: hit.start_ticks,
        originalDuration: hit.duration_ticks,
        originalPitch: hit.pitch,
      }
    } else {
      props.endTransaction()
    }
  }

  function onPointerMove(event: React.PointerEvent) {
    const drag = dragRef.current
    if (!drag?.noteId || !props.track) return
    const { x, y } = pointerPos(event)
    const step = ppq / gridDivision
    const deltaTicks = Math.round(((x - drag.startX) / props.timeline.pxPerBeat) * ppq)
    const deltaPitch = Math.round((drag.startY - y) / view.rowHeight)
    mutateTrack(track => {
      const note = track.notes.find(n => n.id === drag.noteId)
      if (!note) return
      if (drag.mode === 'resize') {
        note.duration_ticks = Math.max(step, snap(drag.originalDuration + deltaTicks, step))
      } else if (drag.mode === 'move') {
        note.start_ticks = Math.max(0, snap(drag.originalStart + deltaTicks, step))
        note.pitch = Math.max(MIN_PITCH, Math.min(MAX_PITCH, drag.originalPitch + deltaPitch))
      }
      track.notes.sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch)
    }, true)
  }

  function onPointerUp(event: React.PointerEvent) {
    if (dragRef.current) {
      dragRef.current = null
      props.endTransaction()
    }
    canvasRef.current?.releasePointerCapture(event.pointerId)
  }

  function onDoubleClick(event: React.MouseEvent) {
    if (!props.track) return
    const rect = canvasRef.current!.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top
    const hit = hitNote(x, y)
    if (hit) {
      setEditing({ note: hit, x, y, value: hit.lyric })
    }
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

  function onKeyDown(event: React.KeyboardEvent) {
    if ((event.key === 'Delete' || event.key === 'Backspace') && selectedNoteId) {
      props.beginTransaction()
      mutateTrack(track => { track.notes = track.notes.filter(n => n.id !== selectedNoteId) }, true)
      props.endTransaction()
      setSelectedNoteId(null)
    }
  }

  return (
    <div className="piano-roll-shell">
      <div className="editor-toolbar">
        <div className="tool-group">
          <button className={tool === 'select' ? 'tool active' : 'tool'} onClick={() => setTool('select')} title="Select/move (V)">➤</button>
          <button className={tool === 'pencil' ? 'tool active' : 'tool'} onClick={() => setTool('pencil')} title="Note brush (B)">✎</button>
          <button className={tool === 'erase' ? 'tool active' : 'tool'} onClick={() => setTool('erase')} title="Eraser (E)">⌫</button>
        </div>
        <label>Grid
          <select value={gridDivision} onChange={e => setGridDivision(Number(e.target.value))}>
            <option value={1}>1/4</option><option value={2}>1/8</option><option value={4}>1/16</option><option value={8}>1/32</option>
          </select>
        </label>
        <label>Zoom<input type="range" min="32" max="360" value={props.timeline.pxPerBeat} onChange={e => props.onTimelineChange({ ...props.timeline, pxPerBeat: Number(e.target.value) })} /></label>
        <label>Row<input type="range" min="8" max="28" value={view.rowHeight} onChange={e => setView(v => ({ ...v, rowHeight: Number(e.target.value) }))} /></label>
        <div className="editor-hint">Ctrl+wheel zoom · Shift+wheel pitch scroll · Double-click lyric</div>
      </div>
      <div className="piano-roll-wrap" ref={wrapRef} tabIndex={0} onKeyDown={onKeyDown}>
        <canvas
          ref={canvasRef}
          className="piano-roll-canvas"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onDoubleClick={onDoubleClick}
          onWheel={onWheel}
          onContextMenu={e => e.preventDefault()}
        />
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
      </div>
    </div>
  )
}
