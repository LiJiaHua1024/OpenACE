import { useCallback, useEffect, useRef, useState } from 'react'
import { api, importAudio, importMidi, importUstx, renderFileUrl } from './api'
import ArrangementView from './components/ArrangementView'
import AutomationLane from './components/AutomationLane'
import PianoRoll from './components/PianoRoll'
import RenderPanel from './components/RenderPanel'
import TrackList from './components/TrackList'
import TempoLane from './components/TempoLane'
import TransportBar from './components/TransportBar'
import { crossfadeGainAt, crossfadeIntervals } from './crossfade'
import { canonicalJson } from './renderFingerprint'
import { barTicks, beatUnitTicks, secondsBetweenTicks, secondsToTicks, tickDurationSeconds, ticksToSeconds } from './tempo'
import type { AudioClip, LoudnessReading, Project, RenderJob, TimelineState, Track } from './types'

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value))
}

const decodedPlaybackBuffers = new Map<string, Promise<AudioBuffer>>()
let sharedPlaybackContext: AudioContext | null = null
let sharedDecodeContext: OfflineAudioContext | null = null

function prewarmPlaybackContext(): AudioContext {
  const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext
  if (!sharedPlaybackContext || sharedPlaybackContext.state === 'closed') sharedPlaybackContext = new AudioContextClass() as AudioContext
  return sharedPlaybackContext
}

function playbackContext(): AudioContext {
  const ctx = prewarmPlaybackContext()
  if (ctx.state === 'suspended') ctx.resume().catch(() => {})
  return ctx
}


async function ensurePlaybackContextRunning(ctx: AudioContext): Promise<boolean> {
  if (ctx.state === 'running') return true
  if (ctx.state === 'closed') return false
  const resumed = await Promise.race([
    ctx.resume().then(() => true).catch(() => false),
    new Promise<boolean>(resolve => window.setTimeout(() => resolve(false), 1500)),
  ])
  return resumed && String(ctx.state) === 'running'
}

function closeSharedPlaybackContext() {
  const ctx = sharedPlaybackContext
  sharedPlaybackContext = null
  if (ctx && ctx.state !== 'closed') void ctx.close().catch(() => {})
}

function playbackDecodeContext(): BaseAudioContext {
  if (!sharedDecodeContext) sharedDecodeContext = new OfflineAudioContext(1, 1, 44100)
  return sharedDecodeContext
}

function decodePlaybackBuffer(ctx: BaseAudioContext, url: string): Promise<AudioBuffer> {
  let cached = decodedPlaybackBuffers.get(url)
  if (!cached) {
    cached = fetch(url)
      .then(response => {
        if (!response.ok) throw new Error(`audio fetch failed: ${response.status}`)
        return response.arrayBuffer()
      })
      .then(bytes => ctx.decodeAudioData(bytes))
    decodedPlaybackBuffers.set(url, cached)
    cached.catch(() => decodedPlaybackBuffers.delete(url))
  }
  return cached
}

function playbackAudioSnapshot(project: Project): string {
  return JSON.stringify({
    bpm: project.bpm,
    time_signature: project.time_signature,
    tempo_map: project.tempo_map,
    tracks: project.tracks.map(track => ({
      id: track.id,
      mute: track.mute,
      solo: track.solo,
      volume: track.volume,
      pan: track.pan,
      mix_automation: { volume: track.automation?.volume || [], pan: track.automation?.pan || [] },
      render_path: track.render_path,
      clips: (track.clips || []).map(clip => ({
        id: clip.id,
        path: clip.path,
        start_ticks: clip.start_ticks,
        offset_ticks: clip.offset_ticks,
        duration_ticks: clip.duration_ticks,
        fade_in_ticks: clip.fade_in_ticks,
        fade_out_ticks: clip.fade_out_ticks,
        gain_db: clip.gain_db,
      })),
    })),
  })
}

interface PlaybackGraph {
  project: Project
  sources: AudioBufferSourceNode[]
  transitionGains: GainNode[]
  analysers: Record<string, AnalyserNode>
  masterAnalyser?: AnalyserNode
  loudnessFeed?: GainNode
  startTicks: number
  startContextTime: number
}

interface PlaybackState {
  startMs: number
  startTicks: number
  startContextTime: number
  raf: number
  sources: AudioBufferSourceNode[]
  transitionGains: GainNode[]
  ctx?: AudioContext
  starting?: boolean
  generation: number
  analysers: Record<string, AnalyserNode>
  masterAnalyser?: AnalyserNode
  loudnessNode?: AudioWorkletNode
  loudnessSink?: GainNode
  loudnessFeed?: GainNode
  loudness: LoudnessReading
  pendingGraph?: PlaybackGraph
  timingProject?: Project
}

function emptyLoudnessReading(): LoudnessReading {
  return { available: false, exact48k: false, sampleRate: 0, momentary: -120, shortTerm: -120, maxMomentary: -120, maxShortTerm: -120, history: [] }
}

function analyserPeakLevel(analyser?: AnalyserNode): number {
  if (!analyser) return 0
  const data = new Uint8Array(analyser.fftSize)
  analyser.getByteTimeDomainData(data)
  let peak = 0
  for (const value of data) peak = Math.max(peak, Math.abs(value - 128) / 128)
  return peak
}

function mixEnvelopeValueAt(points: { ticks: number; value: number }[], ticks: number, fallback: number): number {
  if (!points.length) return fallback
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
  return fallback
}

function scheduleTrackMixAutomation(
  param: AudioParam,
  ctx: AudioContext,
  project: Project,
  track: Track,
  key: 'volume' | 'pan',
  fallback: number,
  scheduleOffsetSeconds: number,
  baseClock = ctx.currentTime,
) {
  const points = [...(((track.automation as any)?.[key] || []) as { ticks: number; value: number }[])].sort((a, b) => a.ticks - b.ticks)
  param.cancelScheduledValues(baseClock)
  const startTicks = Math.max(0, secondsToTicks(project, scheduleOffsetSeconds))
  const valueAt = (ticks: number) => {
    const raw = mixEnvelopeValueAt(points, ticks, fallback)
    return key === 'pan' ? Math.max(-1, Math.min(1, raw)) : Math.max(0, Math.min(2, raw))
  }
  param.setValueAtTime(valueAt(startTicks), baseClock)
  if (!points.length) return
  const eventTicks = new Set<number>()
  for (let index = 0; index < points.length - 1; index++) {
    const left = Math.max(0, Math.round(points[index].ticks))
    const right = Math.max(0, Math.round(points[index + 1].ticks))
    eventTicks.add(left)
    eventTicks.add(right)
    // Musical-time linear interpolation is not exactly linear in seconds inside tempo ramps.
    // Subdivide long segments enough that AudioParam timelines track ramped tempo truthfully.
    const divisions = Math.min(32, Math.max(1, Math.ceil((right - left) / Math.max(1, project.ppq / 16))))
    for (let step = 1; step < divisions; step++) eventTicks.add(Math.round(left + (right - left) * step / divisions))
  }
  if (points.length) eventTicks.add(Math.max(0, Math.round(points[points.length - 1].ticks)))
  let lastClock = baseClock
  for (const ticks of Array.from(eventTicks).sort((a, b) => a - b)) {
    if (ticks <= startTicks + 0.001) continue
    const clock = baseClock + ticksToSeconds(project, ticks) - scheduleOffsetSeconds
    if (!Number.isFinite(clock) || clock <= baseClock + 0.002 || clock <= lastClock + 0.0005) continue
    param.linearRampToValueAtTime(valueAt(ticks), clock)
    lastClock = clock
  }
}

function undoSemanticSignature(project: Project): string {
  const copy = JSON.parse(JSON.stringify(project)) as Project
  copy.updated_at = 0
  for (const track of copy.tracks) {
    delete (track as any).render_path
    delete (track as any).render_fingerprint
    ;(track as any).render_revision = 0
    if ((track as any).reference_voice_path === undefined) (track as any).reference_voice_path = null
    if ((track as any).openutau_singer === undefined) (track as any).openutau_singer = ''
    if ((track as any).openutau_phonemizer === undefined) (track as any).openutau_phonemizer = ''
    if ((track as any).midi_channel === undefined) (track as any).midi_channel = null
    if ((track as any).midi_program === undefined) (track as any).midi_program = null
    if ((track as any).created_by_job_id === undefined) (track as any).created_by_job_id = null
    const automation = (track as any).automation || ((track as any).automation = {})
    for (const lane of ['pitch_cents', 'dynamic', 'air', 'falsetto', 'tension', 'energy', 'volume', 'pan']) {
      if (automation[lane] === undefined) automation[lane] = []
      for (const point of automation[lane] || []) if ((point as any).curve === undefined) (point as any).curve = 'linear'
    }
    for (const clip of (track as any).clips || []) {
      if ((clip as any).duration_ticks === undefined) (clip as any).duration_ticks = null
      if ((clip as any).offset_ticks === undefined) (clip as any).offset_ticks = 0
      if ((clip as any).fade_in_ticks === undefined) (clip as any).fade_in_ticks = 0
      if ((clip as any).fade_out_ticks === undefined) (clip as any).fade_out_ticks = 0
      if ((clip as any).gain_db === undefined) (clip as any).gain_db = 0
      if ((clip as any).label === undefined) (clip as any).label = ''
      if ((clip as any).transcribed_lyrics === undefined) (clip as any).transcribed_lyrics = []
      if ((clip as any).created_by_job_id === undefined) (clip as any).created_by_job_id = null
    }
    for (const breath of (track as any).breaths || []) {
      if ((breath as any).intensity === undefined) (breath as any).intensity = 1
      if ((breath as any).timbre === undefined) (breath as any).timbre = 'natural'
    }
    for (const note of track.notes) {
      ;(note as any).phonemes = []
      if ((note as any).lyric === undefined) (note as any).lyric = ''
      if ((note as any).velocity === undefined) (note as any).velocity = 90
      if ((note as any).pitch_curve === undefined) (note as any).pitch_curve = []
      if ((note as any).pitch_snap_first === undefined) (note as any).pitch_snap_first = true
      if ((note as any).vibrato === undefined) (note as any).vibrato = null
      if ((note as any).techniques === undefined) (note as any).techniques = []
    }
  }
  return canonicalJson(copy)
}

export default function App() {
  const [project, setProject] = useState<Project | null>(null)
  const [selectedTrackId, setSelectedTrackId] = useState<string>()
  const [playheadTicks, setPlayheadTicks] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [timeline, setTimeline] = useState<TimelineState>({ scrollTicks: 0, pxPerBeat: 112, gridDivision: Number(window.localStorage.getItem('openace_grid_division') || 4) })
  const [repaintRange, setRepaintRange] = useState({ start: 0, end: 0 })
  const [sourceAudio, setSourceAudio] = useState('')
  const [sourceClipId, setSourceClipId] = useState<string | undefined>()
  const [loopRange, setLoopRange] = useState<{ start: number; end: number } | null>(null)
  const [loopEnabled, setLoopEnabled] = useState(false)
  const [followPlayback, setFollowPlayback] = useState(() => window.localStorage.getItem('openace_follow_playback') !== 'off')
  const [metronomeEnabled, setMetronomeEnabled] = useState(() => window.localStorage.getItem('openace_metronome') === 'on')
  const metronomeEnabledRef = useRef(false)
  const metronomeTimer = useRef<number | null>(null)
  const metronomeSessions = useRef<{ id: number; project: Project; startTicks: number; startContextTime: number; endContextTime?: number; scheduled: Set<number> }[]>([])
  const metronomeNodes = useRef<{ sessionId: number; osc: OscillatorNode; gain: GainNode; at: number; end: number }[]>([])
  const metronomeSession = useRef(0)
  metronomeEnabledRef.current = metronomeEnabled
  const [jobs, setJobs] = useState<RenderJob[]>([])
  const [projectList, setProjectList] = useState<{ id: string; title: string; bpm?: number; track_count?: number; updated_at?: number; pinned?: boolean; tags?: string[]; folders?: string[] }[]>([])
  const [past, setPast] = useState<Project[]>([])
  const [future, setFuture] = useState<Project[]>([])
  const [error, setError] = useState('')
  const [saveState, setSaveState] = useState<'saved'|'saving'|'error'>('saved')
  const [saveError, setSaveError] = useState('')
  const [importingAudio, setImportingAudio] = useState(false)
  const projectRef = useRef<Project | null>(null)
  const transactionBase = useRef<Project | null>(null)
  const undoAncestry = useRef<string[]>([])
  const lastDirectEdit = useRef<{ key: string; time: number }>({ key: '', time: 0 })
  const locallyDeletingProjectId = useRef<string | null>(null)
  const saveTimer = useRef<number | null>(null)
  const playback = useRef<PlaybackState>({ startMs: 0, startTicks: 0, startContextTime: 0, raf: 0, sources: [], transitionGains: [], starting: false, generation: 0, analysers: {}, loudness: emptyLoudnessReading() })
  const playbackSnapshotRef = useRef('')
  const playbackRebuildTimer = useRef<number | null>(null)
  const loopRestarting = useRef(false)
  const pendingLoopRestart = useRef<{ startTicks: number; endTicks: number; boundaryClock: number; scheduling: boolean } | null>(null)
  const loopRangeRef = useRef<{ start: number; end: number } | null>(null)
  const loopEnabledRef = useRef(false)
  const playbackClockProbe = useRef({ clock: -1, wall: 0 })
  loopRangeRef.current = loopRange
  loopEnabledRef.current = loopEnabled

  const setProjectRef = useCallback((value: Project | null) => {
    projectRef.current = value
    if (value?.id) window.localStorage.setItem('openace_current_project_id', value.id)
    setProject(value)
  }, [])

  const saveVersion = useRef(0)
  const saveChain = useRef<Promise<void>>(Promise.resolve())
  const saveProjectNow = useCallback(async (next: Project) => {
    if (saveTimer.current) {
      window.clearTimeout(saveTimer.current)
      saveTimer.current = null
    }
    const version = ++saveVersion.current
    setSaveState('saving')
    setSaveError('')
    const request = saveChain.current.catch(() => {}).then(() => api.saveProject(next))
    saveChain.current = request.then(() => undefined, () => undefined)
    try {
      await request
      if (saveVersion.current === version) setSaveState('saved')
    } catch (e: any) {
      if (saveVersion.current === version) {
        const raw = e?.message || String(e)
        const readable = raw.match(/"detail":"([^"]+)"/)?.[1] || raw.replace(/^\d+: /, '')
        setSaveState('error')
        setSaveError(readable)
        setError(`save failed: ${readable}`)
      }
    }
  }, [])

  const scheduleSave = useCallback((next: Project) => {
    if (saveTimer.current) window.clearTimeout(saveTimer.current)
    saveTimer.current = window.setTimeout(() => { void saveProjectNow(next) }, 350)
  }, [saveProjectNow])

  const applyLoopFromProject = useCallback((target: Project) => {
    const raw = target.metadata?.playback_loop
    if (raw && Number.isFinite(raw.start) && Number.isFinite(raw.end) && raw.end > raw.start) {
      setLoopRange({ start: Math.round(raw.start), end: Math.round(raw.end) })
      setLoopEnabled(Boolean(raw.enabled))
    } else {
      setLoopRange(null)
      setLoopEnabled(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function boot() {
      try {
        const list = await api.listProjects()
        let current: Project
        const rememberedId = window.localStorage.getItem('openace_current_project_id')
        const remembered = rememberedId && list.some(item => item.id === rememberedId) ? rememberedId : null
        if (list.length) current = await api.getProject(remembered || list[0].id)
        else current = await api.createProject('Untitled OpenACE Project')
        if (!current.tracks.length) {
          const track = await api.addTrack(current.id, { name: 'Vocal 1', type: 'vocal', language: 'zh', color: '#7c5cff' })
          current = await api.getProject(current.id)
          current.tracks = current.tracks.length ? current.tracks : [track]
        }
        if (!cancelled) {
          setProjectList(list)
          setProjectRef(current)
          applyLoopFromProject(current)
          setSelectedTrackId(current.tracks[0]?.id)
        }
        const initialJobs = await api.jobs()
        if (!cancelled) setJobs(initialJobs)
      } catch (e: any) {
        if (!cancelled) setError(e.message || String(e))
      }
    }
    boot()
    return () => { cancelled = true }
  }, [setProjectRef, applyLoopFromProject])

  const rememberUndoSignature = useCallback((target: Project) => {
    const signature = undoSemanticSignature(target)
    undoAncestry.current = [...undoAncestry.current.filter(item => item !== signature), signature].slice(-80)
  }, [])

  useEffect(() => {
    const source = new EventSource('/api/events')
    source.addEventListener('project_updated', event => {
      try {
        const data = JSON.parse((event as MessageEvent).data)
        const incoming = data.payload?.project
        if (incoming) {
          setProjectList(current => {
            const metadata = incoming.metadata || {}
            const summary = {
              id: incoming.id,
              title: incoming.title,
              bpm: incoming.bpm,
              track_count: incoming.tracks?.length,
              updated_at: incoming.updated_at,
              pinned: Boolean(metadata.pinned),
              tags: Array.isArray(metadata.tags) ? metadata.tags : [],
              folders: Array.isArray(metadata.folders) ? metadata.folders : [],
            }
            const next = current.some(item => item.id === incoming.id)
              ? current.map(item => item.id === incoming.id ? summary : item)
              : [summary, ...current]
            return [...next].sort((a, b) => Number(Boolean(b.pinned)) - Number(Boolean(a.pinned)) || (b.updated_at || 0) - (a.updated_at || 0))
          })
        }
        if (incoming && projectRef.current && incoming.id === projectRef.current.id && incoming.updated_at > projectRef.current.updated_at) {
          const signature = undoSemanticSignature(incoming)
          if (!undoAncestry.current.includes(signature)) {
            setPast([])
            setFuture([])
          }
          rememberUndoSignature(incoming)
          setProjectRef(incoming)
          applyLoopFromProject(incoming)
        }
      } catch {}
    })
    source.addEventListener('project_deleted', event => {
      try {
        const data = JSON.parse((event as MessageEvent).data)
        const deletedId = data.payload?.project_id
        if (!deletedId) return
        setProjectList(current => current.filter(item => item.id !== deletedId))
        if (projectRef.current?.id === deletedId && locallyDeletingProjectId.current !== deletedId) {
          void (async () => {
            const list = await api.listProjects()
            const next = list.length ? await api.getProject(list[0].id) : await api.createProject('Untitled OpenACE Project')
            setProjectList(list.length ? list : [{ id: next.id, title: next.title }])
            setProjectRef(next)
            applyLoopFromProject(next)
            setSelectedTrackId(next.tracks[0]?.id)
            setPast([]); setFuture([]); setPlayheadTicks(0)
          })()
        }
      } catch {}
    })
    source.addEventListener('render_job', event => {
      try {
        const data = JSON.parse((event as MessageEvent).data)
        const job = data.payload as RenderJob
        setJobs(current => [job, ...current.filter(j => j.id !== job.id)])
      } catch {}
    })
    return () => source.close()
  }, [setProjectRef, applyLoopFromProject])

  useEffect(() => {
    const timer = window.setInterval(() => {
      api.jobs().then(setJobs).catch(() => {})
    }, 1800)
    return () => window.clearInterval(timer)
  }, [])

  const updateProject = useCallback((mutator: (next: Project) => void, transient = true) => {
    const current = projectRef.current
    if (!current) return
    const next = clone(current)
    mutator(next)
    next.updated_at = Date.now() / 1000
    if (!transient) {
      const now = performance.now()
      const key = mutator.toString()
      if (key !== lastDirectEdit.current.key || now - lastDirectEdit.current.time > 900) {
        setPast(items => [...items.slice(-80), clone(current)])
        setFuture([])
      }
      lastDirectEdit.current = { key, time: now }
      rememberUndoSignature(next)
    }
    setProjectRef(next)
    scheduleSave(next)
  }, [scheduleSave, setProjectRef, rememberUndoSignature])

  const persistLoopState = useCallback((range: { start: number; end: number } | null, enabled: boolean) => {
    updateProject(next => {
      const metadata = { ...(next.metadata || {}) }
      if (range && range.end > range.start) {
        metadata.playback_loop = { start: Math.round(range.start), end: Math.round(range.end), enabled }
      } else {
        delete metadata.playback_loop
      }
      next.metadata = metadata
    }, true)
  }, [updateProject])

  const beginTransaction = useCallback(() => {
    transactionBase.current = projectRef.current ? clone(projectRef.current) : null
  }, [])

  const endTransaction = useCallback(() => {
    const base = transactionBase.current
    const current = projectRef.current
    transactionBase.current = null
    if (!base || !current) return
    if (JSON.stringify(base) !== JSON.stringify(current)) {
      setPast(items => [...items.slice(-80), base])
      setFuture([])
      rememberUndoSignature(current)
      scheduleSave(current)
    }
  }, [scheduleSave, rememberUndoSignature])

  const undo = useCallback(() => {
    const current = projectRef.current
    if (!current || !past.length) return
    const previous = past[past.length - 1]
    setPast(items => items.slice(0, -1))
    setFuture(items => [...items, clone(current)])
    rememberUndoSignature(previous)
    setProjectRef(previous)
    applyLoopFromProject(previous)
    void saveProjectNow(previous)
  }, [past, setProjectRef, applyLoopFromProject, saveProjectNow, rememberUndoSignature])

  const redo = useCallback(() => {
    const current = projectRef.current
    if (!current || !future.length) return
    const next = future[future.length - 1]
    setFuture(items => items.slice(0, -1))
    setPast(items => [...items, clone(current)])
    rememberUndoSignature(next)
    setProjectRef(next)
    applyLoopFromProject(next)
    void saveProjectNow(next)
  }, [future, setProjectRef, applyLoopFromProject, saveProjectNow, rememberUndoSignature])


  const changeSourceAudio = useCallback((path: string, clipId?: string) => {
    setSourceAudio(path)
    setSourceClipId(clipId)
  }, [])

  const openProject = useCallback(async (projectId: string) => {
    try {
      playback.current.sources.forEach(source => { try { source.stop() } catch {} })
      playback.current.sources = []
      playback.current.transitionGains = []
      cancelAnimationFrame(playback.current.raf)
      setPlaying(false)
      setPlayheadTicks(0)
      setSourceAudio('')
      setSourceClipId(undefined)
      const next = await api.getProject(projectId)
      setProjectRef(next)
      applyLoopFromProject(next)
      setSelectedTrackId(next.tracks[0]?.id)
      setPast([]); setFuture([])
    } catch (e: any) { setError(e.message || String(e)) }
  }, [setProjectRef, applyLoopFromProject])

  const createNewProject = useCallback(async () => {
    try {
      const next = await api.createProject('Untitled OpenACE Project')
      const list = await api.listProjects()
      setProjectList(list)
      setProjectRef(next)
      applyLoopFromProject(next)
      setSelectedTrackId(next.tracks[0]?.id)
      setPlayheadTicks(0); setPast([]); setFuture([])
      setSourceAudio('')
      setSourceClipId(undefined)
      locallyDeletingProjectId.current = null
    } catch (e: any) { setError(e.message || String(e)); locallyDeletingProjectId.current = null }
  }, [setProjectRef, applyLoopFromProject])


  const duplicateProjectById = useCallback(async (projectId?: string) => {
    const sourceId = projectId || projectRef.current?.id
    if (!sourceId) return
    try {
      const next = await api.duplicateProject(sourceId)
      setProjectList(await api.listProjects())
      setProjectRef(next)
      applyLoopFromProject(next)
      setSelectedTrackId(next.tracks[0]?.id)
      setPast([]); setFuture([])
    } catch (e: any) { setError(e.message || String(e)) }
  }, [setProjectRef, applyLoopFromProject])

  const deleteProjectById = useCallback(async (projectId?: string) => {
    const current = projectRef.current
    const targetId = projectId || current?.id
    if (!targetId) return
    const targetTitle = targetId === current?.id ? current.title : (projectList.find(item => item.id === targetId)?.title || targetId)
    if (!window.confirm(`Delete project “${targetTitle}”? This cannot be undone.`)) return
    try {
      if (targetId === current?.id) locallyDeletingProjectId.current = targetId
      await api.deleteProject(targetId)
      let list = await api.listProjects()
      if (targetId !== current?.id) {
        setProjectList(list)
        return
      }
      let next: Project
      if (list.length) next = await api.getProject(list[0].id)
      else {
        next = await api.createProject('Untitled OpenACE Project')
        list = await api.listProjects()
      }
      setProjectList(list)
      setProjectRef(next)
      applyLoopFromProject(next)
      setSelectedTrackId(next.tracks[0]?.id)
      setPlayheadTicks(0); setPast([]); setFuture([])
    } catch (e: any) { setError(e.message || String(e)) }
  }, [projectList, setProjectRef, applyLoopFromProject])

  const setArrangementLoop = useCallback((range: { start: number; end: number } | null) => {
    if (range && range.end > range.start) {
      setLoopRange(range)
      setLoopEnabled(true)
      persistLoopState(range, true)
    } else {
      setLoopRange(null)
      setLoopEnabled(false)
      persistLoopState(null, false)
    }
  }, [persistLoopState])

  const toggleLoop = useCallback(() => {
    const existing = loopRangeRef.current
    if (existing && existing.end > existing.start) {
      const enabled = !loopEnabledRef.current
      setLoopEnabled(enabled)
      persistLoopState(existing, enabled)
      return
    }
    const current = projectRef.current
    if (!current) return
    const span = barTicks(current)
    const start = Math.floor(playheadTicks / span) * span
    const range = { start, end: start + span }
    setLoopRange(range)
    setLoopEnabled(true)
    persistLoopState(range, true)
  }, [playheadTicks, persistLoopState])

  const updateProjectOrganization = useCallback(async (projectId: string, patch: { pinned?: boolean; tags?: string[]; folders?: string[] }) => {
    try {
      const updated = await api.updateProjectOrganization(projectId, patch)
      setProjectList(await api.listProjects())
      const current = projectRef.current
      if (current?.id === projectId) setProjectRef({ ...current, metadata: updated.metadata || {} })
    } catch (e: any) { setError(e.message || String(e)) }
  }, [setProjectRef])

  const selectedTrack = project?.tracks.find(t => t.id === selectedTrackId) || project?.tracks[0]

  const clearMetronome = useCallback(() => {
    metronomeSession.current += 1
    if (metronomeTimer.current !== null) window.clearInterval(metronomeTimer.current)
    metronomeTimer.current = null
    metronomeSessions.current = []
    const nodes = metronomeNodes.current.splice(0)
    nodes.forEach(({ osc, gain }) => {
      try { osc.stop(0) } catch {}
      try { osc.disconnect() } catch {}
      try { gain.disconnect() } catch {}
    })
  }, [])

  const scheduleMetronome = useCallback((targetProject: Project, startTicks = playback.current.startTicks, startContextTime = playback.current.startContextTime, endContextTime?: number, replace = true) => {
    if (replace) clearMetronome()
    const ctx = playback.current.ctx
    if (!ctx || !metronomeEnabledRef.current) return
    const session = {
      id: ++metronomeSession.current,
      project: targetProject,
      startTicks,
      startContextTime,
      endContextTime,
      scheduled: new Set<number>(),
    }
    metronomeSessions.current.push(session)
    const scheduleAhead = () => {
      if (!metronomeEnabledRef.current || playback.current.ctx !== ctx) return
      const horizon = ctx.currentTime + 2.25
      for (const item of [...metronomeSessions.current]) {
        const unit = beatUnitTicks(item.project)
        const numerator = Math.max(1, item.project.time_signature.numerator)
        const transportStartSeconds = ticksToSeconds(item.project, item.startTicks)
        const elapsed = Math.max(0, ctx.currentTime - item.startContextTime)
        const nowTicks = ctx.currentTime < item.startContextTime
          ? item.startTicks
          : secondsToTicks(item.project, transportStartSeconds + elapsed)
        let tick = Math.max(0, Math.floor(nowTicks / unit) * unit)
        if (tick < nowTicks - 1) tick += unit
        for (let count = 0; count < 96; count++, tick += unit) {
          const at = item.startContextTime + ticksToSeconds(item.project, tick) - transportStartSeconds
          if (item.endContextTime !== undefined && at >= item.endContextTime - 0.0005) break
          if (at > horizon) break
          if (at < ctx.currentTime + 0.01 || item.scheduled.has(tick)) continue
          item.scheduled.add(tick)
          const osc = ctx.createOscillator()
          const gain = ctx.createGain()
          const downbeat = Math.round(tick / unit) % numerator === 0
          osc.frequency.value = downbeat ? 1760 : 1175
          gain.gain.setValueAtTime(0.0001, at)
          gain.gain.exponentialRampToValueAtTime(downbeat ? 0.22 : 0.14, at + 0.003)
          gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.055)
          osc.connect(gain).connect(ctx.destination)
          metronomeNodes.current.push({ sessionId: item.id, osc, gain, at, end: at + 0.075 })
          osc.start(at)
          osc.stop(at + 0.065)
        }
        for (const tickValue of Array.from(item.scheduled)) {
          const at = item.startContextTime + ticksToSeconds(item.project, tickValue) - transportStartSeconds
          if (at < ctx.currentTime - 0.2) item.scheduled.delete(tickValue)
        }
      }
      metronomeSessions.current = metronomeSessions.current.filter(item => item.endContextTime === undefined || item.endContextTime >= ctx.currentTime - 0.3)
      metronomeNodes.current = metronomeNodes.current.filter(node => node.end >= ctx.currentTime - 0.2)
    }
    scheduleAhead()
    if (metronomeTimer.current === null) metronomeTimer.current = window.setInterval(scheduleAhead, 180)
  }, [clearMetronome])

  const capMetronomeSessionsAt = useCallback((clock: number) => {
    for (const session of metronomeSessions.current) {
      session.endContextTime = Math.min(session.endContextTime ?? Number.POSITIVE_INFINITY, clock)
      const transportStartSeconds = ticksToSeconds(session.project, session.startTicks)
      for (const tick of Array.from(session.scheduled)) {
        const at = session.startContextTime + ticksToSeconds(session.project, tick) - transportStartSeconds
        if (at >= clock - 0.0005) session.scheduled.delete(tick)
      }
    }
    const canceled = metronomeNodes.current.filter(node => node.at >= clock - 0.0005)
    metronomeNodes.current = metronomeNodes.current.filter(node => node.at < clock - 0.0005)
    canceled.forEach(({ osc, gain }) => {
      try { osc.stop(0) } catch {}
      try { osc.disconnect() } catch {}
      try { gain.disconnect() } catch {}
    })
  }, [])

  const discardPendingLoopGraph = useCallback(() => {
    const pending = playback.current.pendingGraph
    if (pending) {
      pending.sources.forEach(source => {
        try { source.stop(0) } catch {}
        try { source.disconnect() } catch {}
      })
      pending.transitionGains.forEach(gain => { try { gain.disconnect() } catch {} })
      try { pending.masterAnalyser?.disconnect() } catch {}
      if (pending.loudnessFeed && playback.current.loudnessNode) {
        try { pending.loudnessFeed.disconnect(playback.current.loudnessNode) } catch {}
      }
    }
    playback.current.pendingGraph = undefined
    pendingLoopRestart.current = null
  }, [])

  const stopActiveSourcesAt = useCallback((clock: number) => {
    playback.current.sources.forEach(source => {
      try { source.stop(clock) } catch {}
    })
  }, [])

  const commitPendingLoopGraph = useCallback(() => {
    const pending = playback.current.pendingGraph
    const meta = pendingLoopRestart.current
    if (!pending || !meta) return false
    const oldMasterAnalyser = playback.current.masterAnalyser
    const oldLoudnessFeed = playback.current.loudnessFeed
    const loudnessNode = playback.current.loudnessNode
    playback.current.sources.forEach(source => { try { source.stop() } catch {} })
    playback.current.sources = pending.sources
    playback.current.transitionGains = pending.transitionGains
    playback.current.analysers = pending.analysers
    playback.current.masterAnalyser = pending.masterAnalyser
    playback.current.loudnessFeed = pending.loudnessFeed
    playback.current.startTicks = meta.startTicks
    playback.current.startContextTime = meta.boundaryClock
    playback.current.timingProject = pending.project
    playback.current.startMs = performance.now() - Math.max(0, ((playback.current.ctx?.currentTime || meta.boundaryClock) - meta.boundaryClock) * 1000)
    playback.current.pendingGraph = undefined
    pendingLoopRestart.current = null
    window.setTimeout(() => {
      try { oldMasterAnalyser?.disconnect() } catch {}
      if (oldLoudnessFeed && loudnessNode) {
        try { oldLoudnessFeed.disconnect(loudnessNode) } catch {}
      }
    }, 120)
    return true
  }, [])

  const stopPlaybackAudio = useCallback(() => {
    clearMetronome()
    discardPendingLoopGraph()
    playback.current.generation += 1
    playback.current.sources.forEach(source => { try { source.stop() } catch {} })
    playback.current.sources = []
    playback.current.transitionGains = []
    const oldMasterAnalyser = playback.current.masterAnalyser
    const loudnessFeed = playback.current.loudnessFeed
    const loudnessNode = playback.current.loudnessNode
    if (loudnessFeed && loudnessNode) {
      try { loudnessFeed.disconnect(loudnessNode) } catch {}
    }
    playback.current.loudnessFeed = undefined
    playback.current.analysers = {}
    playback.current.masterAnalyser = undefined
    window.setTimeout(() => {
      try { oldMasterAnalyser?.disconnect() } catch {}
    }, 30)
    // Keep the context alive: decoder and node creation are reused across transport starts.
    playback.current.ctx = undefined
  }, [clearMetronome, discardPendingLoopGraph])

  const invalidatePlaybackOutput = useCallback(() => {
    playback.current.loudnessNode = undefined
    playback.current.loudnessSink = undefined
    playback.current.ctx = undefined
    playbackClockProbe.current = { clock: -1, wall: 0 }
    closeSharedPlaybackContext()
  }, [])

  const getTrackLevel = useCallback((trackId: string) => analyserPeakLevel(playback.current.analysers[trackId]), [])
  const getMasterLevel = useCallback(() => analyserPeakLevel(playback.current.masterAnalyser), [])
  const getLoudness = useCallback(() => playback.current.loudness, [])
  const resetLoudness = useCallback(() => {
    playback.current.loudnessNode?.port.postMessage({ type: 'reset' })
    playback.current.loudness = { ...emptyLoudnessReading(), available: playback.current.loudness.available, exact48k: playback.current.loudness.exact48k, sampleRate: playback.current.loudness.sampleRate }
  }, [])


  const preloadPlaybackMedia = useCallback((targetProject: Project) => {
    const urls = Array.from(new Set(targetProject.tracks.flatMap(track => [
      renderFileUrl(track.render_path),
      ...(track.clips || []).map(clip => renderFileUrl(clip.path)),
    ]).filter((url): url is string => Boolean(url))))
    if (!urls.length) return
    const decodeContext = playbackDecodeContext()
    prewarmPlaybackContext()
    for (const url of urls) void decodePlaybackBuffer(decodeContext, url).catch(() => {})
  }, [])

  useEffect(() => {
    if (!project) return
    const timer = window.setTimeout(() => preloadPlaybackMedia(project), 80)
    return () => window.clearTimeout(timer)
  }, [project, preloadPlaybackMedia])


  useEffect(() => {
    const warmOutput = () => { playbackContext() }
    window.addEventListener('pointerdown', warmOutput, { once: true })
    window.addEventListener('keydown', warmOutput, { once: true })
    return () => {
      window.removeEventListener('pointerdown', warmOutput)
      window.removeEventListener('keydown', warmOutput)
    }
  }, [])

  const fadeOutPlaybackGraph = useCallback((fadeSeconds = 0.09) => {
    discardPendingLoopGraph()
    const ctx = playback.current.ctx
    const oldSources = playback.current.sources
    const oldGains = playback.current.transitionGains
    const oldMasterAnalyser = playback.current.masterAnalyser
    const oldLoudnessFeed = playback.current.loudnessFeed
    const persistentLoudnessNode = playback.current.loudnessNode
    playback.current.sources = []
    playback.current.transitionGains = []
    playback.current.loudnessFeed = undefined
    const cleanup = () => {
      oldGains.forEach(gain => { try { gain.disconnect() } catch {} })
      try { oldMasterAnalyser?.disconnect() } catch {}
      if (oldLoudnessFeed && persistentLoudnessNode) {
        try { oldLoudnessFeed.disconnect(persistentLoudnessNode) } catch {}
      }
    }
    if (!ctx || !oldSources.length) {
      cleanup()
      return
    }
    const now = ctx.currentTime
    oldSources.forEach((source, index) => {
      const gain = oldGains[index]
      try {
        if (gain) {
          const current = Math.max(0.0001, gain.gain.value || 1)
          const curve = new Float32Array(17)
          for (let step = 0; step < curve.length; step++) curve[step] = current * Math.cos((step / (curve.length - 1)) * Math.PI / 2)
          gain.gain.cancelScheduledValues(now)
          gain.gain.setValueAtTime(current, now)
          gain.gain.setValueCurveAtTime(curve, now, fadeSeconds)
        }
        source.stop(now + fadeSeconds + 0.03)
      } catch {}
    })
    window.setTimeout(cleanup, Math.ceil((fadeSeconds + 0.08) * 1000))
  }, [discardPendingLoopGraph])

  const schedulePlayback = useCallback(async (targetProject: Project, startTicks: number, continuous = false, transitionFadeInSeconds = 0, deferredStartClock?: number) => {
    const deferred = deferredStartClock !== undefined && Number.isFinite(deferredStartClock)
    const generation = deferred ? playback.current.generation : playback.current.generation + 1
    if (!deferred) playback.current.generation = generation
    const rendered = targetProject.tracks
      .map(track => {
        const clipPaths = new Set((track.clips || []).map(clip => clip.path))
        const sources: { path: string; startTicks: number; offsetTicks: number; durationTicks: number | null; fadeInTicks: number; fadeOutTicks: number; gainDb: number; clip: AudioClip | null }[] = (track.clips || []).map(clip => ({
          path: clip.path,
          startTicks: clip.start_ticks || 0,
          offsetTicks: clip.offset_ticks || 0,
          durationTicks: clip.duration_ticks || null,
          fadeInTicks: clip.fade_in_ticks || 0,
          fadeOutTicks: clip.fade_out_ticks || 0,
          gainDb: clip.gain_db || 0,
          clip,
        }))
        if (track.render_path && !clipPaths.has(track.render_path)) sources.push({ path: track.render_path, startTicks: 0, offsetTicks: 0, durationTicks: null, fadeInTicks: 0, fadeOutTicks: 0, gainDb: 0, clip: null })
        return { ...track, playbackSources: sources }
      })
      .filter(track => !track.mute && track.playbackSources.length)
    const anySolo = rendered.some(track => track.solo)
    const audible = rendered.filter(track => !anySolo || track.solo)
    const ctx = playbackContext()
    if (!(await ensurePlaybackContextRunning(ctx))) {
      setError('Audio output could not start. Check the browser/system audio device, then press Play again.')
      return false
    }
    playback.current.ctx = ctx
    if (!deferred) {
      playback.current.startMs = performance.now()
      playback.current.startTicks = startTicks
      playback.current.startContextTime = ctx?.currentTime || 0
      if (!continuous) playback.current.timingProject = targetProject
    }
    const tracksAndBuffers = await Promise.all(audible.flatMap(track => track.playbackSources.map(async sourceSpec => {
      const url = renderFileUrl(sourceSpec.path)
      if (!url || !ctx) return null
      try {
        const buffer = await decodePlaybackBuffer(ctx, url)
        return { track, buffer, sourceStartTicks: sourceSpec.startTicks, sourceOffsetTicks: sourceSpec.offsetTicks, sourceDurationTicks: sourceSpec.durationTicks, fadeInTicks: sourceSpec.fadeInTicks, fadeOutTicks: sourceSpec.fadeOutTicks, gainDb: sourceSpec.gainDb, clip: sourceSpec.clip }
      } catch { return null }
    })))
    if (playback.current.generation !== generation) return false
    const nextAnalysers: Record<string, AnalyserNode> = {}
    const masterInput = ctx.createGain()
    const masterAnalyser = ctx.createAnalyser()
    masterAnalyser.fftSize = 512
    masterInput.connect(masterAnalyser)
    masterAnalyser.connect(ctx.destination)
    let nextLoudnessFeed: GainNode | undefined
    try {
      if (ctx.audioWorklet) {
        await ctx.audioWorklet.addModule('/loudness-worklet.js')
        if (playback.current.generation !== generation) return false
        let loudnessNode = playback.current.loudnessNode
        let loudnessSink = playback.current.loudnessSink
        if (!loudnessNode || !loudnessSink) {
          loudnessNode = new AudioWorkletNode(ctx, 'openace-loudness', { numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [2] })
          loudnessSink = ctx.createGain()
          loudnessSink.gain.value = 0
          loudnessNode.connect(loudnessSink)
          loudnessSink.connect(ctx.destination)
          loudnessNode.port.onmessage = event => {
            if (playback.current.loudnessNode !== loudnessNode) return
            const data = event.data || {}
            const reading = playback.current.loudness
            reading.available = true
            reading.exact48k = Boolean(data.exact48k)
            reading.sampleRate = Number(data.sampleRate || ctx.sampleRate)
            reading.momentary = Number(data.momentary ?? -120)
            reading.shortTerm = Number(data.shortTerm ?? -120)
            reading.maxMomentary = Math.max(reading.maxMomentary, reading.momentary)
            reading.maxShortTerm = Math.max(reading.maxShortTerm, reading.shortTerm)
            reading.history.push({ time: performance.now() / 1000, momentary: reading.momentary, shortTerm: reading.shortTerm })
            if (reading.history.length > 180) reading.history.splice(0, reading.history.length - 180)
          }
          playback.current.loudnessNode = loudnessNode
          playback.current.loudnessSink = loudnessSink
        }
        masterInput.connect(loudnessNode)
        nextLoudnessFeed = masterInput
      }
    } catch {
      playback.current.loudness.available = false
    }
    if (!continuous && !deferred) {
      playback.current.startMs = performance.now()
      playback.current.startTicks = startTicks
      playback.current.startContextTime = ctx?.currentTime || 0
    }
    const baseClock = deferred ? deferredStartClock! : ctx.currentTime
    if (deferred && baseClock <= ctx.currentTime + 0.003) {
      try { masterInput.disconnect() } catch {}
      try { masterAnalyser.disconnect() } catch {}
      return false
    }
    const scheduleOffsetSeconds = continuous && !deferred
      ? ticksToSeconds(targetProject, playback.current.startTicks) + (baseClock - playback.current.startContextTime)
      : ticksToSeconds(targetProject, startTicks)
    const trackInputs = new Map<string, GainNode>()
    const inputForTrack = (track: Track) => {
      const existing = trackInputs.get(track.id)
      if (existing) return existing
      const input = ctx.createGain()
      const volume = ctx.createGain()
      volume.gain.value = track.volume
      const panner = ctx.createStereoPanner()
      panner.pan.value = track.pan
      scheduleTrackMixAutomation(volume.gain, ctx, targetProject, track, 'volume', track.volume, scheduleOffsetSeconds, baseClock)
      scheduleTrackMixAutomation(panner.pan, ctx, targetProject, track, 'pan', track.pan, scheduleOffsetSeconds, baseClock)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 512
      input.connect(volume).connect(panner).connect(analyser)
      analyser.connect(masterInput)
      nextAnalysers[track.id] = analyser
      trackInputs.set(track.id, input)
      return input
    }
    const nextSources: AudioBufferSourceNode[] = []
    const nextTransitionGains: GainNode[] = []
    for (const item of tracksAndBuffers) {
      if (!item || !ctx) continue
      const source = ctx.createBufferSource()
      source.buffer = item.buffer
      const transitionGain = ctx.createGain()
      transitionGain.gain.value = transitionFadeInSeconds > 0.001 ? 0.0001 : 1
      const gain = ctx.createGain()
      const clipGain = Math.pow(10, (item.gainDb || 0) / 20)
      const baseGain = clipGain
      gain.gain.value = baseGain
      source.connect(transitionGain).connect(gain).connect(inputForTrack(item.track))
      const sourceStartSeconds = ticksToSeconds(targetProject, item.sourceStartTicks)
      const sourceOffsetSeconds = secondsBetweenTicks(targetProject, item.sourceStartTicks - item.sourceOffsetTicks, item.sourceStartTicks)
      const clipDurationSeconds = item.sourceDurationTicks
        ? tickDurationSeconds(targetProject, item.sourceStartTicks, item.sourceDurationTicks)
        : Math.max(0, item.buffer.duration - sourceOffsetSeconds)
      const localOffset = scheduleOffsetSeconds - sourceStartSeconds
      const clipStartClock = baseClock - localOffset
      const fadeInSeconds = tickDurationSeconds(targetProject, item.sourceStartTicks, item.fadeInTicks || 0)
      const clipEndTicks = item.sourceStartTicks + (item.sourceDurationTicks || 0)
      const fadeOutSeconds = item.sourceDurationTicks
        ? tickDurationSeconds(targetProject, clipEndTicks - (item.fadeOutTicks || 0), item.fadeOutTicks || 0)
        : tickDurationSeconds(targetProject, item.sourceStartTicks, item.fadeOutTicks || 0)
      const positionNow = Math.max(0, localOffset)
      const fadeGainAt = (position: number) => {
        const manual = Math.min(
          fadeInSeconds ? Math.max(0, Math.min(1, position / fadeInSeconds)) : 1,
          fadeOutSeconds ? Math.max(0, Math.min(1, (clipDurationSeconds - position) / fadeOutSeconds)) : 1,
        )
        if (!item.clip) return manual
        const timelinePosition = secondsToTicks(targetProject, sourceStartSeconds + position)
        return manual * crossfadeGainAt(item.track, item.clip, timelinePosition)
      }
      const automationPositions = new Set<number>([positionNow, clipDurationSeconds])
      if (fadeInSeconds > 0.001) automationPositions.add(fadeInSeconds)
      if (fadeOutSeconds > 0.001) automationPositions.add(clipDurationSeconds - fadeOutSeconds)
      if (item.clip) {
        for (const interval of crossfadeIntervals(item.track, item.clip)) {
          for (let step = 0; step <= 12; step++) {
            const ticks = interval.startTicks + (interval.endTicks - interval.startTicks) * step / 12
            automationPositions.add(secondsBetweenTicks(targetProject, item.sourceStartTicks, ticks))
          }
        }
      }
      const audibleStartClock = Math.max(baseClock, clipStartClock + positionNow)
      gain.gain.setValueAtTime(Math.max(0.0001, baseGain * fadeGainAt(positionNow)), audibleStartClock)
      let lastClock = audibleStartClock
      for (const position of Array.from(automationPositions).sort((a, b) => a - b)) {
        if (position <= positionNow + 0.0001 || position > clipDurationSeconds + 0.0001) continue
        const clock = clipStartClock + position
        if (clock <= baseClock + 0.001 || clock <= lastClock + 0.0005) continue
        gain.gain.linearRampToValueAtTime(Math.max(0.0001, baseGain * fadeGainAt(position)), clock)
        lastClock = clock
      }
      if (localOffset >= 0 && localOffset < clipDurationSeconds) {
        const audioOffset = sourceOffsetSeconds + localOffset
        const remaining = Math.max(0.01, clipDurationSeconds - localOffset)
        source.start(baseClock, Math.min(Math.max(0, item.buffer.duration - 0.03), audioOffset), remaining)
      } else if (localOffset < 0) {
        source.start(baseClock - localOffset, sourceOffsetSeconds, Math.max(0.01, clipDurationSeconds))
      }
      if (transitionFadeInSeconds > 0.001) {
        const now = baseClock
        const curve = new Float32Array(17)
        for (let step = 0; step < curve.length; step++) curve[step] = Math.max(0.0001, Math.sin((step / (curve.length - 1)) * Math.PI / 2))
        transitionGain.gain.setValueCurveAtTime(curve, now, transitionFadeInSeconds)
      }
      nextSources.push(source)
      nextTransitionGains.push(transitionGain)
    }
    if (playback.current.generation !== generation) return false
    const graph: PlaybackGraph = {
      project: targetProject,
      sources: nextSources,
      transitionGains: nextTransitionGains,
      analysers: nextAnalysers,
      masterAnalyser,
      loudnessFeed: nextLoudnessFeed,
      startTicks,
      startContextTime: baseClock,
    }
    if (deferred) {
      playback.current.pendingGraph = graph
      scheduleMetronome(targetProject, startTicks, baseClock, undefined, false)
    } else {
      playback.current.sources = nextSources
      playback.current.transitionGains = nextTransitionGains
      playback.current.analysers = nextAnalysers
      playback.current.masterAnalyser = masterAnalyser
      playback.current.loudnessFeed = nextLoudnessFeed
      playback.current.timingProject = targetProject
      scheduleMetronome(targetProject)
    }
    return true
  }, [scheduleMetronome])

  const seekTransport = useCallback((ticks: number) => {
    const target = Math.max(0, Math.floor(ticks))
    setPlayheadTicks(target)
    if (!playing) return
    const current = projectRef.current
    if (!current) return
    stopPlaybackAudio()
    void schedulePlayback(current, target)
  }, [playing, schedulePlayback, stopPlaybackAudio])

  useEffect(() => {
    if (!playing || !project) {
      playbackSnapshotRef.current = ''
      if (playbackRebuildTimer.current) {
        window.clearTimeout(playbackRebuildTimer.current)
        playbackRebuildTimer.current = null
      }
      return
    }
    const snapshot = playbackAudioSnapshot(project)
    if (!playbackSnapshotRef.current) {
      playbackSnapshotRef.current = snapshot
      return
    }
    if (snapshot === playbackSnapshotRef.current) return
    playbackSnapshotRef.current = snapshot
    if (playbackRebuildTimer.current) window.clearTimeout(playbackRebuildTimer.current)
    const attemptRebuild = () => {
      playbackRebuildTimer.current = null
      void (async () => {
        const current = projectRef.current
        if (!current || !playing) return
        const ctx = playback.current.ctx
        const activeLoop = loopEnabledRef.current ? loopRangeRef.current : null
        const currentTimingProject = playback.current.timingProject || current
        let boundaryClock: number | null = null
        if (ctx && activeLoop) {
          const epochStartSeconds = ticksToSeconds(currentTimingProject, playback.current.startTicks)
          boundaryClock = playback.current.startContextTime + ticksToSeconds(currentTimingProject, activeLoop.end) - epochStartSeconds
        }
        const timeUntilBoundary = ctx && boundaryClock !== null ? boundaryClock - ctx.currentTime : Number.POSITIVE_INFINITY
        if (pendingLoopRestart.current || (timeUntilBoundary > 0 && timeUntilBoundary < 0.55)) {
          playbackRebuildTimer.current = window.setTimeout(attemptRebuild, 80)
          return
        }
        const elapsed = ctx ? ctx.currentTime - playback.current.startContextTime : (performance.now() - playback.current.startMs) / 1000
        const timingProject = playback.current.timingProject || current
        const ticks = secondsToTicks(timingProject, ticksToSeconds(timingProject, playback.current.startTicks) + elapsed)
        fadeOutPlaybackGraph()
        await schedulePlayback(current, ticks, true, 0.09)
      })()
    }
    playbackRebuildTimer.current = window.setTimeout(attemptRebuild, 120)
  }, [project, playing, schedulePlayback, stopPlaybackAudio, fadeOutPlaybackGraph])

  useEffect(() => {
    if (!playing || !followPlayback || !project) return
    const workspace = document.querySelector<HTMLElement>('.center-workspace')
    const width = Math.max(240, (workspace?.clientWidth || 900) - 64)
    const visibleTicks = (width / Math.max(1, timeline.pxPerBeat)) * project.ppq
    const leadIn = visibleTicks * 0.05
    const leadOut = visibleTicks * 0.85
    const position = playheadTicks - timeline.scrollTicks
    if (position < leadIn || position > leadOut) {
      const targetScroll = Math.max(0, playheadTicks - visibleTicks * 0.18)
      if (Math.abs(targetScroll - timeline.scrollTicks) > 1) {
        setTimeline(current => ({ ...current, scrollTicks: targetScroll }))
      }
    }
  }, [playing, followPlayback, project, playheadTicks, timeline.pxPerBeat, timeline.scrollTicks])

  const previousMetronomeEnabled = useRef(metronomeEnabled)
  useEffect(() => {
    const wasEnabled = previousMetronomeEnabled.current
    previousMetronomeEnabled.current = metronomeEnabled
    if (wasEnabled === metronomeEnabled) return
    if (!metronomeEnabled) {
      clearMetronome()
    } else if (playing && project) {
      scheduleMetronome(project)
    }
  }, [metronomeEnabled, playing, project, clearMetronome, scheduleMetronome])

  const playToggle = useCallback(async () => {
    if (!project) return
    if (playing) {
      setPlaying(false)
      stopPlaybackAudio()
      cancelAnimationFrame(playback.current.raf)
      return
    }
    if (playback.current.starting) return
    playback.current.starting = true
    try {
      playbackSnapshotRef.current = playbackAudioSnapshot(project)
      const scheduled = await schedulePlayback(project, playheadTicks)
      if (!scheduled) {
        stopPlaybackAudio()
        cancelAnimationFrame(playback.current.raf)
        return
      }
      playbackClockProbe.current = playback.current.ctx
        ? { clock: playback.current.ctx.currentTime, wall: performance.now() }
        : { clock: -1, wall: performance.now() }
      cancelAnimationFrame(playback.current.raf)
      const step = () => {
        const current = projectRef.current
        if (!current) return
        const ctx = playback.current.ctx
        if (ctx) {
          const wallNow = performance.now()
          const clockNow = ctx.currentTime
          if (playbackClockProbe.current.clock < 0 || clockNow > playbackClockProbe.current.clock + 0.0001) {
            playbackClockProbe.current = { clock: clockNow, wall: wallNow }
          } else if (wallNow - playbackClockProbe.current.wall > 750) {
            setPlaying(false)
            stopPlaybackAudio()
            cancelAnimationFrame(playback.current.raf)
            invalidatePlaybackOutput()
            setError('Audio output clock stalled; playback was stopped instead of pretending transport time was advancing. Press Play again to rebuild the audio engine.')
            return
          }
        }
        const activeLoop = loopEnabledRef.current ? loopRangeRef.current : null
        const pending = pendingLoopRestart.current
        if (pending && (!activeLoop || pending.startTicks !== activeLoop.start || pending.endTicks !== activeLoop.end)) {
          discardPendingLoopGraph()
          clearMetronome()
          if (ctx && metronomeEnabledRef.current) scheduleMetronome(current)
        }
        if (ctx && pendingLoopRestart.current && ctx.currentTime >= pendingLoopRestart.current.boundaryClock) {
          if (!commitPendingLoopGraph()) pendingLoopRestart.current = null
        }
        const elapsed = ctx ? ctx.currentTime - playback.current.startContextTime : (performance.now() - playback.current.startMs) / 1000
        const timingProject = playback.current.timingProject || current
        let ticks = secondsToTicks(timingProject, ticksToSeconds(timingProject, playback.current.startTicks) + elapsed)
        if (activeLoop && ctx && !pendingLoopRestart.current) {
          const epochStartSeconds = ticksToSeconds(current, playback.current.startTicks)
          const boundaryClock = playback.current.startContextTime + ticksToSeconds(current, activeLoop.end) - epochStartSeconds
          const timeUntilBoundary = boundaryClock - ctx.currentTime
          if (timeUntilBoundary > 0.025 && timeUntilBoundary < 0.45) {
            const pendingRestart = { startTicks: activeLoop.start, endTicks: activeLoop.end, boundaryClock, scheduling: true }
            pendingLoopRestart.current = pendingRestart
            stopActiveSourcesAt(boundaryClock)
            capMetronomeSessionsAt(boundaryClock)
            void schedulePlayback(current, activeLoop.start, false, 0, boundaryClock).then(success => {
              if (!success && pendingLoopRestart.current === pendingRestart) pendingLoopRestart.current = null
            })
          }
        }
        if (activeLoop && ticks >= activeLoop.end && !loopRestarting.current) {
          const activePending = pendingLoopRestart.current
          if (activePending && playback.current.pendingGraph && ctx && ctx.currentTime < activePending.boundaryClock + 0.05) {
            ticks = activeLoop.end
          } else {
            loopRestarting.current = true
            const span = Math.max(1, activeLoop.end - activeLoop.start)
            const restartTicks = activeLoop.start + ((ticks - activeLoop.end) % span)
            ticks = restartTicks
            stopPlaybackAudio()
            void schedulePlayback(current, restartTicks).finally(() => { loopRestarting.current = false })
          }
        }
        setPlayheadTicks(Math.floor(ticks))
        playback.current.raf = requestAnimationFrame(step)
      }
      playback.current.raf = requestAnimationFrame(step)
      setError(current => current.startsWith('Audio output') ? '' : current)
      setPlaying(true)
    } catch (e: any) {
      stopPlaybackAudio()
      cancelAnimationFrame(playback.current.raf)
      setError(e?.message || String(e))
    } finally {
      playback.current.starting = false
    }
  }, [project, playing, playheadTicks, schedulePlayback, stopPlaybackAudio, capMetronomeSessionsAt, clearMetronome, commitPendingLoopGraph, discardPendingLoopGraph, invalidatePlaybackOutput, scheduleMetronome, stopActiveSourcesAt])

  const stop = useCallback(() => {
    setPlaying(false)
    setPlayheadTicks(0)
    stopPlaybackAudio()
    cancelAnimationFrame(playback.current.raf)
  }, [stopPlaybackAudio])

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement
      const isUndoGesture = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z'
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') {
        if (isUndoGesture && target.classList.contains('lyric-editor') && !(target as HTMLInputElement).value) {
          event.preventDefault()
          event.shiftKey ? redo() : undo()
        }
        return
      }
      if (event.code === 'Space') { event.preventDefault(); playToggle() }
      if (!event.ctrlKey && !event.metaKey && !event.altKey && event.key.toLowerCase() === 'l') { event.preventDefault(); toggleLoop() }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); event.shiftKey ? redo() : undo() }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'y') { event.preventDefault(); redo() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [playToggle, toggleLoop, undo, redo])

  function patchTrack(trackId: string, patch: Partial<Track>) {
    updateProject(next => {
      const track = next.tracks.find(t => t.id === trackId)
      if (track) Object.assign(track, patch)
    }, false)
  }


  async function handleImportAudio(file: File) {
    setImportingAudio(true)
    try {
      const imported = await importAudio(file)
      setProjectList(await api.listProjects())
      setProjectRef(imported)
      setSelectedTrackId(imported.tracks[0]?.id)
      setPast([])
      setFuture([])
    } catch (e: any) { setError(e.message || String(e)) }
    finally { setImportingAudio(false) }
  }

  async function handleImportedProject(promise: Promise<Project>) {
    try {
      const imported = await promise
      setProjectList(await api.listProjects())
      setProjectRef(imported)
      setSelectedTrackId(imported.tracks[0]?.id)
      setPast([])
      setFuture([])
    } catch (e: any) { setError(e.message || String(e)) }
  }

  if (!project) {
    return <div className="boot-screen"><div className="brand-mark large">OA</div><div>Loading OpenACE Studio…</div>{error && <div className="error-banner">{error}</div>}</div>
  }

  return (
    <div className="app-shell">
      <TransportBar
        project={project}
        projects={projectList.length ? projectList : [{ id: project.id, title: project.title }]}
        playing={playing}
        playheadTicks={playheadTicks}
        canUndo={past.length > 0}
        canRedo={future.length > 0}
        onPlayToggle={playToggle}
        onStop={stop}
        onSeek={seekTransport}
        loopEnabled={loopEnabled}
        onLoopToggle={toggleLoop}
        followPlayback={followPlayback}
        onFollowToggle={() => setFollowPlayback(value => { const next = !value; window.localStorage.setItem('openace_follow_playback', next ? 'on' : 'off'); return next })}
        metronomeEnabled={metronomeEnabled}
        onMetronomeToggle={() => setMetronomeEnabled(value => { const next = !value; window.localStorage.setItem('openace_metronome', next ? 'on' : 'off'); return next })}
        onTitleChange={title => updateProject(next => { next.title = title }, false)}
        onBpmChange={bpm => updateProject(next => { next.bpm = Math.max(30, Math.min(300, bpm)) }, false)}
        onTimeSignatureChange={(numerator, denominator) => updateProject(next => { next.time_signature = { numerator, denominator } }, false)}
        onUndo={undo}
        onRedo={redo}
        onOpenProject={openProject}
        onNewProject={createNewProject}
        onDuplicateProject={duplicateProjectById}
        onDeleteProject={deleteProjectById}
        onUpdateProjectOrganization={updateProjectOrganization}
        onImportMidi={file => void handleImportedProject(importMidi(file))}
        onImportUstx={file => void handleImportedProject(importUstx(file))}
        onImportAudio={handleImportAudio}
        importingAudio={importingAudio}
        saveState={saveState}
        saveError={saveError}
        onRetrySave={() => projectRef.current && void saveProjectNow(projectRef.current)}
      />
      <div className="workspace-grid">
        <TrackList
          project={project}
          selectedTrackId={selectedTrack?.id}
          onSelect={setSelectedTrackId}
          onAddTrack={type => {
            const id = `track_${crypto.randomUUID().slice(0, 12)}`
            updateProject(next => {
            const index = next.tracks.length + 1
            next.tracks.push({
              id,
              name: type === 'vocal' ? `Vocal ${index}` : `BGM ${index}`,
              type,
              color: type === 'vocal' ? '#7c5cff' : '#2fb996',
              voice_id: 'zero-shot-reference',
              reference_voice_path: null,
              language: 'zh',
              notes: [],
              clips: [],
              automation: { pitch_cents: [], dynamic: [], air: [], falsetto: [], tension: [], energy: [], volume: [], pan: [] },
              breaths: [],
              mute: false,
              solo: false,
              volume: 0.8,
              pan: 0,
              render_path: null,
              render_revision: 0,
            })
            }, false)
            setSelectedTrackId(id)
          }}
          onPatchTrack={patchTrack}
          updateProject={updateProject}
          getTrackLevel={getTrackLevel}
          getMasterLevel={getMasterLevel}
          getLoudness={getLoudness}
          onResetLoudness={resetLoudness}
        />
        <main className="center-workspace">
          <ArrangementView
            project={project}
            selectedTrackId={selectedTrack?.id}
            playheadTicks={playheadTicks}
            onSelect={setSelectedTrackId}
            onSeek={seekTransport}
            beginTransaction={beginTransaction}
            endTransaction={endTransaction}
            updateProject={updateProject}
            timeline={timeline}
            onTimelineChange={setTimeline}
            repaintRange={repaintRange}
            onRepaintRange={setRepaintRange}
            loopRange={loopRange}
            loopEnabled={loopEnabled}
            onLoopRange={setArrangementLoop}
            onSelectClip={clip => changeSourceAudio(clip.path, clip.id)}
          />
          <TempoLane
            project={project}
            timeline={timeline}
            playheadTicks={playheadTicks}
            onTimelineChange={setTimeline}
            beginTransaction={beginTransaction}
            endTransaction={endTransaction}
            updateProject={updateProject}
          />
          <PianoRoll
            project={project}
            track={selectedTrack}
            playheadTicks={playheadTicks}
            onSeek={seekTransport}
            beginTransaction={beginTransaction}
            endTransaction={endTransaction}
            updateProject={updateProject}
            timeline={timeline}
            loopRange={loopRange}
            loopEnabled={loopEnabled}
            onTimelineChange={setTimeline}
          />
          <AutomationLane
            project={project}
            track={selectedTrack}
            playheadTicks={playheadTicks}
            beginTransaction={beginTransaction}
            endTransaction={endTransaction}
            updateProject={updateProject}
            timeline={timeline}
            onTimelineChange={setTimeline}
          />
        </main>
        <RenderPanel
          project={project}
          track={selectedTrack}
          playheadTicks={playheadTicks}
          jobs={jobs}
          repaintRange={repaintRange}
          onRepaintRange={setRepaintRange}
          sourceAudio={sourceAudio}
          sourceClipId={sourceClipId}
          onSourceAudioChange={changeSourceAudio}
          onPatchTrack={patchTrack}
          updateProject={updateProject}
          onJobCreated={job => setJobs(current => [job, ...current.filter(j => j.id !== job.id)])}
        />
      </div>
      {error && <div className="error-banner global" onClick={() => setError('')}>{error}</div>}
    </div>
  )
}
