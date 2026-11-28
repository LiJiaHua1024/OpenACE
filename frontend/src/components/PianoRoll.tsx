import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { Note, Project, TimelineState, Track } from '../types'
import { barTicks as musicalBarTicks, tickDurationSeconds } from '../tempo'
import { zoomTimelineAt } from '../timelineZoom'

const KEY_WIDTH = 64
const RULER_HEIGHT = 30
const VELOCITY_HEIGHT = 54
const MIN_PITCH = 24
const MAX_PITCH = 96

type Tool = 'select' | 'pencil' | 'erase' | 'pitch' | 'pitchBrush'

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
  mode: 'move' | 'resize' | 'resize-start' | 'create' | 'marquee' | 'velocity' | null
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
  loopRange?: { start: number; end: number } | null
  loopEnabled?: boolean
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

let auditionContext: AudioContext | null = null

function auditionNotePitch(pitch: number) {
  const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext
  if (!AudioContextClass) return
  if (!auditionContext || auditionContext.state === 'closed') auditionContext = new AudioContextClass() as AudioContext
  if (auditionContext.state === 'suspended') void auditionContext.resume().catch(() => {})
  const now = auditionContext.currentTime
  const osc = auditionContext.createOscillator()
  const gain = auditionContext.createGain()
  osc.type = 'triangle'
  osc.frequency.setValueAtTime(440 * Math.pow(2, (pitch - 69) / 12), now)
  gain.gain.setValueAtTime(0.0001, now)
  gain.gain.exponentialRampToValueAtTime(0.075, now + 0.012)
  gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.22)
  osc.connect(gain).connect(auditionContext.destination)
  osc.start(now)
  osc.stop(now + 0.24)
  osc.onended = () => {
    osc.disconnect()
    gain.disconnect()
  }
}

function batchLyricTokens(text: string, language: string): string[] {
  const source = text.replace(/\r/g, ' ').trim()
  if (!source) return []
  if (language.toLowerCase().startsWith('en')) return source.split(/\s+/).filter(Boolean)
  const tokens: string[] = []
  let latin = ''
  const flushLatin = () => {
    if (latin) tokens.push(latin)
    latin = ''
  }
  for (const char of Array.from(source)) {
    if (/\s/u.test(char)) {
      flushLatin()
      continue
    }
    if (char === '-') {
      flushLatin()
      tokens.push('-')
      continue
    }
    if (/[\u3400-\u9fff]/u.test(char)) {
      flushLatin()
      tokens.push(char)
      continue
    }
    if (/[\p{Script=Latin}\p{Number}'_]/u.test(char)) {
      latin += char
      continue
    }
    // CJK punctuation is prosody markup, not a sung syllable; the backend phonemizer skips it too.
    flushLatin()
  }
  flushLatin()
  return tokens
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
  const [auditionEnabled, setAuditionEnabled] = useState(() => window.localStorage.getItem('openace_note_audition') !== 'off')
  const lastAuditionRef = useRef<{ pitch: number; at: number } | null>(null)
  const newlyCreatedNoteIdRef = useRef<string | null>(null)
  const [view, setView] = useState<ViewState>({ rowHeight: 15, topPitch: 79 })
  const [selectedNoteIds, setSelectedNoteIds] = useState<string[]>([])
  const [editing, setEditing] = useState<{ note: Note; x: number; y: number; value: string } | null>(null)
  const skipLyricBlurCommitRef = useRef(false)
  const [marquee, setMarquee] = useState<{ x1: number; y1: number; x2: number; y2: number } | null>(null)
  const [menu, setMenu] = useState<{ x: number; y: number; noteId?: string; splitTicks?: number } | null>(null)
  const [splitError, setSplitError] = useState<string | null>(null)
  const [vibratoEditor, setVibratoEditor] = useState<{ noteId: string; x: number; y: number } | null>(null)
  const [phonemeEditor, setPhonemeEditor] = useState<{ noteId: string; x: number; y: number; value: string; error?: string } | null>(null)
  const [batchLyricEditor, setBatchLyricEditor] = useState<{ value: string } | null>(null)
  const dragRef = useRef<DragState | null>(null)
  const pitchDragRef = useRef<{ noteId: string; pointIndex: number } | null>(null)
  const pitchStrokeRef = useRef<{ points: { ticks: number; value: number; curve: string }[]; minTick: number; maxTick: number } | null>(null)
  const clipboardRef = useRef<Note[]>([])
  const [clipboardCount, setClipboardCount] = useState(0)
  const [pitchReadout, setPitchReadout] = useState<string | null>(null)
  const ppq = props.project.ppq
  const gridDivision = Math.max(1, props.timeline.gridDivision ?? 4)
  const selectedSet = new Set(selectedNoteIds)

  const xForTick = useCallback((ticks: number) => KEY_WIDTH + ((ticks - props.timeline.scrollTicks) / ppq) * props.timeline.pxPerBeat, [props.timeline.scrollTicks, props.timeline.pxPerBeat, ppq])
  const tickForX = useCallback((x: number) => Math.max(0, props.timeline.scrollTicks + ((x - KEY_WIDTH) / props.timeline.pxPerBeat) * ppq), [props.timeline.scrollTicks, props.timeline.pxPerBeat, ppq])
  const yForPitch = useCallback((pitch: number) => RULER_HEIGHT + (view.topPitch - pitch) * view.rowHeight, [view])
  const pitchForY = useCallback((y: number) => Math.round(view.topPitch - (y - RULER_HEIGHT) / view.rowHeight), [view])
  const continuousPitchForY = useCallback((y: number) => view.topPitch - (y - RULER_HEIGHT) / view.rowHeight, [view])

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

      const step = ppq / gridDivision
      const beatTicks = ppq
      const barTicks = musicalBarTicks(props.project)
      const startTick = Math.floor(props.timeline.scrollTicks / step) * step
      const endTick = props.timeline.scrollTicks + ((width - KEY_WIDTH) / props.timeline.pxPerBeat) * ppq + ppq
      for (let tick = startTick; tick <= endTick; tick += step) {
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

      if (props.loopRange && props.loopRange.end > props.loopRange.start) {
        const sx = xForTick(props.loopRange.start)
        const ex = xForTick(props.loopRange.end)
        if (ex >= KEY_WIDTH && sx < width) {
          ctx.fillStyle = props.loopEnabled ? '#55c7ff18' : '#55c7ff0a'
          ctx.fillRect(sx, RULER_HEIGHT, ex - sx, height - RULER_HEIGHT)
          ctx.strokeStyle = props.loopEnabled ? '#61d5ffcc' : '#61d5ff66'
          ctx.lineWidth = 1.4
          ctx.beginPath()
          ctx.moveTo(sx, RULER_HEIGHT); ctx.lineTo(sx, height)
          ctx.moveTo(ex, RULER_HEIGHT); ctx.lineTo(ex, height)
          ctx.stroke()
          ctx.lineWidth = 1
          ctx.fillStyle = props.loopEnabled ? '#a8eaff' : '#6ba9bd'
          ctx.font = '9px Inter, sans-serif'
          ctx.fillText(props.loopEnabled ? 'loop' : 'loop off', Math.max(KEY_WIDTH + 4, sx + 4), 12)
        }
      }

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

          if ((tool === 'pitch' || tool === 'pitchBrush') && props.track.automation?.pitch_cents?.length) {
            const startX = Math.max(x, KEY_WIDTH)
            const endX = Math.min(x + w, width)
            if (endX > startX) {
              ctx.strokeStyle = selected ? '#ffffffff' : '#f2f6ffd9'
              ctx.lineWidth = selected ? 1.9 : 1.4
              ctx.beginPath()
              let firstUserPoint = true
              const sampleStep = Math.max(2, Math.floor(w / 80))
              for (let sx = startX; sx <= endX; sx += sampleStep) {
                const tick = tickForX(sx)
                const cents = pitchAutomationCentsAt(props.track.automation.pitch_cents, tick)
                const py = yForPitch(note.pitch + cents / 100) + view.rowHeight / 2
                if (firstUserPoint) { ctx.moveTo(sx, py); firstUserPoint = false } else ctx.lineTo(sx, py)
              }
              ctx.stroke()
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
  }, [props.project, props.track, props.timeline, props.loopRange, props.loopEnabled, view, selectedNoteIds, marquee, xForTick, yForPitch, ppq, tool])

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

  function pitchAutomationCentsAt(points: { ticks: number; value: number }[], ticks: number): number {
    if (!points.length) return 0
    const ordered = [...points].sort((a, b) => a.ticks - b.ticks)
    if (ticks <= ordered[0].ticks) return ordered[0].value
    if (ticks >= ordered[ordered.length - 1].ticks) return ordered[ordered.length - 1].value
    for (let index = 0; index < ordered.length - 1; index++) {
      const left = ordered[index]
      const right = ordered[index + 1]
      if (left.ticks <= ticks && ticks <= right.ticks) {
        const ratio = (ticks - left.ticks) / Math.max(1, right.ticks - left.ticks)
        return left.value + (right.value - left.value) * ratio
      }
    }
    return 0
  }

  function writePitchBrushAt(x: number, y: number) {
    const stroke = pitchStrokeRef.current
    if (!stroke || !props.track) return
    const rawTick = tickForX(x)
    const note = props.track.notes.find(item => rawTick >= item.start_ticks && rawTick < item.start_ticks + item.duration_ticks)
    if (!note) return
    const ticks = Math.max(0, Math.round(rawTick))
    const cents = Math.max(-600, Math.min(600, Math.round((continuousPitchForY(y) - note.pitch) * 100)))
    stroke.minTick = Math.min(stroke.minTick, ticks)
    stroke.maxTick = Math.max(stroke.maxTick, ticks)
    const last = stroke.points[stroke.points.length - 1]
    if (last && last.ticks === ticks) last.value = cents
    else if (!last || Math.abs(ticks - last.ticks) >= 6 || Math.abs(cents - last.value) >= 3) stroke.points.push({ ticks, value: cents, curve: 'linear' })
    else return
    mutateTrack(track => {
      const outside = track.automation.pitch_cents.filter(point => point.ticks < stroke.minTick || point.ticks > stroke.maxTick)
      const rewritten = new Map(stroke.points.map(point => [point.ticks, point]))
      track.automation.pitch_cents = [...outside, ...rewritten.values()].sort((a, b) => a.ticks - b.ticks)
    }, true)
    setPitchReadout(`${ticks} ticks · ${cents > 0 ? '+' : ''}${cents}¢ user pitch`)
  }

  function mutateTrack(mutator: (track: Track) => void, transient = true) {
    if (!props.track) return
    const trackId = props.track.id
    props.updateProject(project => {
      const track = project.tracks.find(t => t.id === trackId)
      if (track) mutator(track)
    }, transient)
  }

  function resolveNoteOverlaps(track: Track) {
    const ordered = [...track.notes].sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch || a.id.localeCompare(b.id))
    for (let index = ordered.length - 2; index >= 0; index--) {
      const note = ordered[index]
      const next = ordered[index + 1]
      if (note.start_ticks + note.duration_ticks > next.start_ticks) {
        note.duration_ticks = Math.max(0, next.start_ticks - note.start_ticks)
      }
    }
    track.notes = ordered.filter(note => note.duration_ticks > 0)
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
    const cents = Math.max(-600, Math.min(600, point.cents))
    const y = yForPitch(note.pitch + cents / 100) + view.rowHeight / 2
    return { x, y }
  }

  function pitchPointAt(note: Note, x: number, y: number) {
    const rect = noteRect(note)
    const durationMs = Math.max(1, noteDurationMs(note))
    const ratio = Math.max(0, Math.min(1, (x - rect.x - 2) / Math.max(1, rect.w - 4)))
    const continuousPitch = view.topPitch - (y - RULER_HEIGHT - view.rowHeight / 2) / view.rowHeight
    const cents = Math.max(-600, Math.min(600, (continuousPitch - note.pitch) * 100))
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


  function audition(pitch: number, force = false) {
    if (!auditionEnabled) return
    const now = performance.now()
    const last = lastAuditionRef.current
    if (!force && last && now - last.at < 90) return
    lastAuditionRef.current = { pitch, at: now }
    auditionNotePitch(pitch)
  }

  function toggleAudition() {
    setAuditionEnabled(current => {
      const next = !current
      window.localStorage.setItem('openace_note_audition', next ? 'on' : 'off')
      return next
    })
  }

  function onPointerDown(event: React.PointerEvent) {
    if (!props.track || event.button === 2) return
    setMenu(null)
    const { x, y } = pointerPos(event)
    canvasRef.current?.setPointerCapture(event.pointerId)
    if (y < RULER_HEIGHT) {
      props.onSeek(snap(tickForX(x), ppq / gridDivision))
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

    if (tool === 'pitchBrush') {
      props.beginTransaction()
      pitchStrokeRef.current = { points: [], minTick: Number.POSITIVE_INFINITY, maxTick: Number.NEGATIVE_INFINITY }
      writePitchBrushAt(x, y)
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
      newlyCreatedNoteIdRef.current = id
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
          pitch_snap_first: true,
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
      audition(pitch, true)
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
      const resizeEnd = x > nx + nw - 7
      const resizeStart = !resizeEnd && x < nx + 7
      props.beginTransaction()
      dragRef.current = {
        mode: resizeEnd ? 'resize' : resizeStart ? 'resize-start' : 'move',
        noteId: hit.id,
        startX: x,
        startY: y,
        originalStart: hit.start_ticks,
        originalDuration: hit.duration_ticks,
        originalPitch: hit.pitch,
        originals: snapshotsFor(nextSelection.length ? nextSelection : [hit.id]),
      }
      audition(hit.pitch, true)
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

    if (pitchStrokeRef.current) {
      writePitchBrushAt(x, y)
      return
    }

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
      } else if (drag.mode === 'resize-start') {
        const minStart = Math.min(...ids.map(id => originals[id].start))
        const maxShrink = Math.min(...ids.map(id => originals[id].duration - step))
        const allowedDelta = Math.max(-minStart, Math.min(deltaTicks, maxShrink))
        for (const id of ids) {
          const note = track.notes.find(n => n.id === id)
          if (note) {
            note.start_ticks = originals[id].start + allowedDelta
            note.duration_ticks = originals[id].duration - allowedDelta
          }
        }
      } else if (drag.mode === 'move') {
        const minStart = Math.min(...ids.map(id => originals[id].start))
        const allowedTickDelta = Math.max(deltaTicks, -minStart)
        const minPitch = Math.min(...ids.map(id => originals[id].pitch))
        const maxPitch = Math.max(...ids.map(id => originals[id].pitch))
        const allowedPitchDelta = Math.max(MIN_PITCH - minPitch, Math.min(MAX_PITCH - maxPitch, deltaPitch))
        if (drag.noteId && originals[drag.noteId]) audition(originals[drag.noteId].pitch + allowedPitchDelta)
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
    if (pitchStrokeRef.current) {
      props.endTransaction()
      pitchStrokeRef.current = null
      window.setTimeout(() => setPitchReadout(null), 1600)
    }
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
    if (hadDrag && (hadDrag.mode === 'move' || hadDrag.mode === 'resize' || hadDrag.mode === 'resize-start')) {
      mutateTrack(track => resolveNoteOverlaps(track), true)
    }
    if (hadDrag && hadDrag.mode !== 'marquee') props.endTransaction()
    dragRef.current = null
    setMarquee(null)
    canvasRef.current?.releasePointerCapture(event.pointerId)
    const createdId = newlyCreatedNoteIdRef.current
    newlyCreatedNoteIdRef.current = null
    if (createdId && props.track) {
      const created = props.track.notes.find(note => note.id === createdId)
      if (created) {
        const rect = noteRect(created)
        setEditing({ note: created, x: rect.x + rect.w / 2, y: rect.y + rect.h / 2, value: created.lyric })
      }
    }
  }

  function onDoubleClick(event: React.MouseEvent) {
    if (!props.track) return
    const { x, y } = pointerPos(event)
    const hit = hitNote(x, y)
    if (hit) setEditing({ note: hit, x, y, value: hit.lyric })
  }

  useEffect(() => {
    if (editing && props.track && !props.track.notes.some(note => note.id === editing.note.id)) setEditing(null)
  }, [editing, props.track])

  function commitLyric(advance: -1 | 0 | 1 = 0) {
    if (!editing) return
    const value = editing.value.trim()
    const noteId = editing.note.id
    let nextNote: Note | null = null
    if (advance && props.track) {
      const ordered = [...props.track.notes].sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch)
      const index = ordered.findIndex(note => note.id === noteId)
      nextNote = ordered[index + advance] || null
    }
    const currentLyric = props.track?.notes.find(note => note.id === noteId)?.lyric ?? ''
    if (value !== currentLyric) {
      props.beginTransaction()
      mutateTrack(track => {
        const note = track.notes.find(n => n.id === noteId)
        if (note) {
          note.lyric = value
          note.phonemes = []
        }
      }, true)
      props.endTransaction()
    }
    if (nextNote) {
      const rect = noteRect(nextNote)
      setEditing({ note: nextNote, x: rect.x + rect.w / 2, y: rect.y + rect.h / 2, value: nextNote.lyric })
    } else {
      setEditing(null)
    }
  }

  function selectedNotes(): Note[] {
    if (!props.track) return []
    return props.track.notes.filter(note => selectedSet.has(note.id)).sort((a, b) => a.start_ticks - b.start_ticks)
  }

  function batchTargetNotes(): Note[] {
    if (!props.track) return []
    const selected = selectedNotes()
    return (selected.length ? selected : [...props.track.notes]).sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch)
  }

  function applyBatchLyrics() {
    if (!batchLyricEditor || !props.track) return
    const tokens = batchLyricTokens(batchLyricEditor.value, props.track.language)
    const targets = batchTargetNotes()
    if (!tokens.length || !targets.length || tokens.length !== targets.length) return
    if (['mixed', 'multilingual', 'zh-en', 'en-zh'].includes(props.track.language.toLowerCase()) && /[\u3040-\u30ff]/u.test(batchLyricEditor.value)) return
    props.beginTransaction()
    mutateTrack(track => {
      const ordered = (selectedNoteIds.length ? track.notes.filter(note => selectedSet.has(note.id)) : [...track.notes])
        .sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch)
      for (let index = 0; index < Math.min(tokens.length, ordered.length); index++) {
        ordered[index].lyric = tokens[index]
        ordered[index].phonemes = []
      }
    }, true)
    props.endTransaction()
    setBatchLyricEditor(null)
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
    let survivingIds: string[] = []
    mutateTrack(track => {
      for (const source of clipboard) {
        const note = cloneNote(source)
        note.id = `note_${crypto.randomUUID().slice(0, 12)}`
        note.start_ticks = source.start_ticks + delta
        newIds.push(note.id)
        track.notes.push(note)
      }
      track.notes.sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch)
      resolveNoteOverlaps(track)
      survivingIds = track.notes.filter(note => newIds.includes(note.id)).map(note => note.id)
    }, true)
    setSelectedNoteIds(survivingIds)
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

  async function splitNoteAtTick(noteId: string, splitTicks: number) {
    if (!props.track) return
    const note = props.track.notes.find(item => item.id === noteId)
    if (!note) return
    if (splitTicks <= note.start_ticks || splitTicks >= note.start_ticks + note.duration_ticks) {
      setSplitError('Split position must be inside the note')
      window.setTimeout(() => setSplitError(null), 2400)
      return
    }
    setSplitError(null)
    props.beginTransaction()
    try {
      await api.saveProject(props.project)
      const result = await api.splitNote(props.project.id, props.track.id, noteId, Math.round(splitTicks))
      props.updateProject(project => {
        const track = project.tracks.find(item => item.id === props.track?.id)
        if (!track) return
        track.notes = track.notes.filter(item => item.id !== noteId && item.id !== result.second.id)
        track.notes.push(result.first, result.second)
        track.notes.sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch)
      }, true)
      setSelectedNoteIds([result.first.id, result.second.id])
    } catch (error) {
      const raw = error instanceof Error ? error.message : String(error)
      const detail = raw.match(/"detail":"([^"]+)"/)?.[1] || raw.replace(/^\d+: /, '')
      setSplitError(detail.includes('sustained vowel') ? 'Split must land inside a sustained vowel' : detail)
      window.setTimeout(() => setSplitError(null), 3200)
    } finally {
      props.endTransaction()
    }
  }

  async function mergeSelectedNotes() {
    if (!props.track || selectedNoteIds.length < 2) return
    setSplitError(null)
    props.beginTransaction()
    try {
      await api.saveProject(props.project)
      const merged = await api.mergeNotes(props.project.id, props.track.id, selectedNoteIds)
      props.updateProject(project => {
        const track = project.tracks.find(item => item.id === props.track?.id)
        if (!track) return
        const removed = new Set(selectedNoteIds)
        track.notes = track.notes.filter(item => !removed.has(item.id))
        track.notes.push(merged)
        track.notes.sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch)
      }, true)
      setSelectedNoteIds([merged.id])
    } catch (error) {
      const raw = error instanceof Error ? error.message : String(error)
      const detail = raw.match(/"detail":"([^"]+)"/)?.[1] || raw.replace(/^\d+: /, '')
      setSplitError(detail)
      window.setTimeout(() => setSplitError(null), 3600)
    } finally {
      props.endTransaction()
    }
  }

  function splitSelectedAtPlayhead() {
    if (selectedNoteIds.length !== 1 || !props.track) return
    const note = props.track.notes.find(item => item.id === selectedNoteIds[0])
    if (!note) return
    void splitNoteAtTick(note.id, props.playheadTicks)
  }

  function selectedNoteContainsPlayhead() {
    if (selectedNoteIds.length !== 1 || !props.track) return false
    const note = props.track.notes.find(item => item.id === selectedNoteIds[0])
    return !!note && props.playheadTicks > note.start_ticks && props.playheadTicks < note.start_ticks + note.duration_ticks
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
      resolveNoteOverlaps(track)
    }, true)
    props.endTransaction()
  }

  function onWheel(event: React.WheelEvent) {
    if (event.ctrlKey || event.metaKey) {
      const factor = event.deltaY > 0 ? 0.9 : 1.1
      const rect = event.currentTarget.getBoundingClientRect()
      props.onTimelineChange(zoomTimelineAt(props.timeline, event.clientX - rect.left, KEY_WIDTH, factor, ppq))
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

  function nudgeSelection(direction: 'left' | 'right' | 'up' | 'down', octave = false) {
    if (!props.track || !selectedNoteIds.length) return
    const notes = props.track.notes.filter(note => selectedSet.has(note.id))
    if (!notes.length) return
    props.beginTransaction()
    if (direction === 'left' || direction === 'right') {
      const step = ppq / gridDivision
      const rawDelta = direction === 'left' ? -step : step
      const minStart = Math.min(...notes.map(note => note.start_ticks))
      const delta = Math.max(rawDelta, -minStart)
      mutateTrack(track => {
        for (const note of track.notes) {
          if (selectedSet.has(note.id)) note.start_ticks = Math.max(0, note.start_ticks + delta)
        }
        track.notes.sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch)
        resolveNoteOverlaps(track)
      }, true)
    } else {
      const rawDelta = (direction === 'up' ? 1 : -1) * (octave ? 12 : 1)
      const minPitch = Math.min(...notes.map(note => note.pitch))
      const maxPitch = Math.max(...notes.map(note => note.pitch))
      const delta = Math.max(MIN_PITCH - minPitch, Math.min(MAX_PITCH - maxPitch, rawDelta))
      mutateTrack(track => {
        for (const note of track.notes) {
          if (selectedSet.has(note.id)) note.pitch = Math.max(MIN_PITCH, Math.min(MAX_PITCH, note.pitch + delta))
        }
        track.notes.sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch)
      }, true)
    }
    props.endTransaction()
  }

  function handleEditorKey(event: KeyboardEvent) {
    const target = event.target as HTMLElement
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable) return
    const key = event.key.toLowerCase()
    if (!event.ctrlKey && !event.metaKey && !event.altKey && event.key.startsWith('Arrow')) {
      const direction = { ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down' }[event.key] as 'left' | 'right' | 'up' | 'down' | undefined
      if (direction && selectedNoteIds.length) {
        event.preventDefault()
        nudgeSelection(direction, event.shiftKey)
        return
      }
    }
    if ((event.ctrlKey || event.metaKey) && key === 'j') {
      event.preventDefault(); void mergeSelectedNotes(); return
    }
    if ((event.ctrlKey || event.metaKey) && key === 'a') {
      event.preventDefault()
      setSelectedNoteIds(props.track?.notes.map(note => note.id) || [])
      return
    }
    if ((event.ctrlKey || event.metaKey) && key === 'e') {
      event.preventDefault(); splitSelectedAtPlayhead(); return
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
      if (key === '1') setTool('pitchBrush')
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
    setMenu({ x, y, noteId: hit?.id, splitTicks: hit ? Math.round(tickForX(x)) : undefined })
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
          <button className={tool === 'pitchBrush' ? 'tool active' : 'tool'} onClick={() => setTool('pitchBrush')} title="Freehand user-pitch brush (1); drag across notes to rewrite continuous pitch automation">🖌 Pitch</button>
          <button className={tool === 'pitch' ? 'tool active' : 'tool'} onClick={() => setTool('pitch')} title="Per-note pitch anchor handles (P); Alt+click deletes a handle">∿ Anchor</button>
          <button className={auditionEnabled ? 'tool active' : 'tool'} onClick={toggleAudition} title="Editor note audition preview; not vocal synthesis">♪ Audition</button>
        </div>
        <div className="tool-group edit-actions">
          <button className="tool" onClick={copySelection} disabled={!selectedNoteIds.length} title="Copy (Ctrl+C)">Copy</button>
          <button className="tool" onClick={() => pasteClipboard()} disabled={!clipboardCount} title="Paste at playhead (Ctrl+V)">Paste</button>
          <button className="tool" onClick={duplicateSelection} disabled={!selectedNoteIds.length} title="Duplicate (Ctrl+D)">Dup</button>
          <button className="tool" onClick={quantizeSelection} title="Quantize selection/all (Q)">Quant</button>
          <button className="tool" onClick={splitSelectedAtPlayhead} disabled={!selectedNoteContainsPlayhead()} title="Split selected note at playhead (Ctrl+E)">Split</button>
          <button className="tool" onClick={() => void mergeSelectedNotes()} disabled={selectedNoteIds.length < 2} title="Merge exactly contiguous selected notes (Ctrl+J)">Merge</button>
          <button className="tool" onClick={() => openVibratoEditor()} disabled={selectedNoteIds.length !== 1} title="Edit vibrato for selected note">Vibrato</button>
          <button className="tool" onClick={() => setBatchLyricEditor({ value: '' })} disabled={!props.track?.notes.length} title="Distribute a phrase across selected notes, or all notes when nothing is selected">Lyrics…</button>
        </div>
        <label>Grid
          <select value={gridDivision} onChange={e => { const value = Number(e.target.value); window.localStorage.setItem('openace_grid_division', String(value)); props.onTimelineChange({ ...props.timeline, gridDivision: value }) }}>
            <option value={1}>1/4</option><option value={2}>1/8</option><option value={3}>1/8T</option><option value={4}>1/16</option><option value={6}>1/16T</option><option value={8}>1/32</option>
          </select>
        </label>
        <label>Zoom<input type="range" min="32" max="360" value={props.timeline.pxPerBeat} onChange={e => props.onTimelineChange({ ...props.timeline, pxPerBeat: Number(e.target.value) })} /></label>
        <label>Row<input type="range" min="8" max="28" value={view.rowHeight} onChange={e => setView(v => ({ ...v, rowHeight: Number(e.target.value) }))} /></label>
        <div className="selection-count">{selectedNoteIds.length ? `${selectedNoteIds.length} selected` : ''}</div>
        <div className="pitch-readout">{pitchReadout || ''}</div>
        <div className="editor-hint">V/B/E/P · arrows nudge · Ctrl+C/V/D/E/J · Tab lyric next</div>
      </div>
      <div className="piano-roll-wrap" ref={wrapRef} tabIndex={0}>
        {splitError && <div className="split-error">{splitError}</div>}
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
            <button disabled={!menu.noteId || menu.splitTicks === undefined} onClick={() => menuAction(() => { if (menu.noteId && menu.splitTicks !== undefined) void splitNoteAtTick(menu.noteId, menu.splitTicks) })}>Split here</button>
            <button disabled={!selectedNoteContainsPlayhead()} onClick={() => menuAction(splitSelectedAtPlayhead)}>Split at playhead</button>
            <button disabled={!selectedNoteIds.length} onClick={() => menuAction(copySelection)}>Copy</button>
            <button disabled={!clipboardCount} onClick={() => menuAction(() => pasteClipboard())}>Paste at playhead</button>
            <button disabled={!selectedNoteIds.length} onClick={() => menuAction(duplicateSelection)}>Duplicate</button>
            <button disabled={!selectedNoteIds.length} onClick={() => menuAction(quantizeSelection)}>Quantize</button>
            <button disabled={selectedNoteIds.length < 2} onClick={() => menuAction(() => void mergeSelectedNotes())}>Merge contiguous</button>
            <button disabled={selectedNoteIds.length !== 1} onClick={() => openVibratoEditor(menu.x + 8, menu.y + 8)}>Vibrato…</button>
            <button disabled={selectedNoteIds.length !== 1} onClick={() => openPhonemeEditor(menu.x + 8, menu.y + 8)}>Phonemes…</button>
            <button disabled={!props.track?.notes.length} onClick={() => menuAction(() => setBatchLyricEditor({ value: '' }))}>Batch lyrics…</button>
            <button disabled={!selectedNoteIds.length} className="danger" onClick={() => menuAction(deleteSelection)}>Delete</button>
          </div>
        )}
        {batchLyricEditor && props.track && (() => {
          const targets = batchTargetNotes()
          const tokens = batchLyricTokens(batchLyricEditor.value, props.track.language)
          const mismatch = tokens.length !== targets.length
          const unsupportedJapanese = ['mixed', 'multilingual', 'zh-en', 'en-zh'].includes(props.track.language.toLowerCase()) && /[\u3040-\u30ff]/u.test(batchLyricEditor.value)
          return (
            <div className="batch-lyric-editor">
              <div className="vibrato-header"><strong>Batch lyrics</strong><button onClick={() => setBatchLyricEditor(null)}>×</button></div>
              <textarea
                autoFocus
                value={batchLyricEditor.value}
                placeholder={props.track.language.toLowerCase().startsWith('en') ? 'Type words separated by spaces; use - for melisma continuations' : '输入整句歌词；每个汉字分配到下一个音符，- 表示延音'}
                onChange={event => setBatchLyricEditor({ value: event.target.value })}
                onKeyDown={event => {
                  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') applyBatchLyrics()
                  if (event.key === 'Escape') setBatchLyricEditor(null)
                }}
              />
              <div className="batch-lyric-count">{tokens.length} lyric tokens → {targets.length} {selectedNoteIds.length ? 'selected' : 'track'} notes</div>
              {unsupportedJapanese && <div className="batch-lyric-warning">Japanese script is not supported in Mixed Mandarin/English mode; use Mandarin or English lyric units.</div>}
              {tokens.length > 0 && mismatch && <div className="batch-lyric-warning">'Lyric token count must exactly match the target notes before anything is applied.'</div>}
              <div className="phoneme-actions">
                <button disabled={!tokens.length || !targets.length || mismatch || unsupportedJapanese} title={unsupportedJapanese ? 'Japanese script is not supported in mixed mode' : mismatch ? 'Lyric token count must exactly match target notes' : ''} onClick={applyBatchLyrics}>Apply Ctrl+Enter</button>
                <button onClick={() => setBatchLyricEditor(null)}>Cancel</button>
              </div>
            </div>
          )
        })()}
        {editing && (
          <input
            className="lyric-editor"
            style={{ left: editing.x + 2, top: editing.y + 2 }}
            autoFocus
            value={editing.value}
            onChange={e => setEditing({ ...editing, value: e.target.value })}
            onBlur={() => { if (skipLyricBlurCommitRef.current) return; commitLyric() }}
            onKeyDown={e => { if (e.key === 'Enter') commitLyric(); if (e.key === 'Tab') { e.preventDefault(); skipLyricBlurCommitRef.current = true; window.setTimeout(() => { skipLyricBlurCommitRef.current = false }, 80); commitLyric(e.shiftKey ? -1 : 1) }; if (e.key === 'Escape') setEditing(null) }}
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
