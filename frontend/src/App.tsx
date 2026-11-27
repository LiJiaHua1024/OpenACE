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
import { barTicks, secondsBetweenTicks, secondsToTicks, tickDurationSeconds, ticksToSeconds } from './tempo'
import type { AudioClip, Project, RenderJob, TimelineState, Track } from './types'

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
    tempo_map: project.tempo_map,
    tracks: project.tracks.map(track => ({
      id: track.id,
      mute: track.mute,
      solo: track.solo,
      volume: track.volume,
      pan: track.pan,
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

function analyserPeakLevel(analyser?: AnalyserNode): number {
  if (!analyser) return 0
  const data = new Uint8Array(analyser.fftSize)
  analyser.getByteTimeDomainData(data)
  let peak = 0
  for (const value of data) peak = Math.max(peak, Math.abs(value - 128) / 128)
  return peak
}

export default function App() {
  const [project, setProject] = useState<Project | null>(null)
  const [selectedTrackId, setSelectedTrackId] = useState<string>()
  const [playheadTicks, setPlayheadTicks] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [timeline, setTimeline] = useState<TimelineState>({ scrollTicks: 0, pxPerBeat: 112 })
  const [repaintRange, setRepaintRange] = useState({ start: 0, end: 0 })
  const [loopRange, setLoopRange] = useState<{ start: number; end: number } | null>(null)
  const [loopEnabled, setLoopEnabled] = useState(false)
  const [jobs, setJobs] = useState<RenderJob[]>([])
  const [projectList, setProjectList] = useState<{ id: string; title: string; bpm?: number; track_count?: number; updated_at?: number; pinned?: boolean; tags?: string[]; folders?: string[] }[]>([])
  const [past, setPast] = useState<Project[]>([])
  const [future, setFuture] = useState<Project[]>([])
  const [error, setError] = useState('')
  const [importingAudio, setImportingAudio] = useState(false)
  const projectRef = useRef<Project | null>(null)
  const transactionBase = useRef<Project | null>(null)
  const locallyDeletingProjectId = useRef<string | null>(null)
  const saveTimer = useRef<number | null>(null)
  const playback = useRef<{ startMs: number; startTicks: number; startContextTime: number; raf: number; sources: AudioBufferSourceNode[]; ctx?: AudioContext; starting?: boolean; generation: number; analysers: Record<string, AnalyserNode>; masterAnalyser?: AnalyserNode }>({ startMs: 0, startTicks: 0, startContextTime: 0, raf: 0, sources: [], starting: false, generation: 0, analysers: {} })
  const playbackSnapshotRef = useRef('')
  const playbackRebuildTimer = useRef<number | null>(null)
  const loopRestarting = useRef(false)
  const loopRangeRef = useRef<{ start: number; end: number } | null>(null)
  const loopEnabledRef = useRef(false)
  loopRangeRef.current = loopRange
  loopEnabledRef.current = loopEnabled

  const setProjectRef = useCallback((value: Project | null) => {
    projectRef.current = value
    setProject(value)
  }, [])

  const scheduleSave = useCallback((next: Project) => {
    if (saveTimer.current) window.clearTimeout(saveTimer.current)
    saveTimer.current = window.setTimeout(() => {
      api.saveProject(next).catch(e => setError(`save failed: ${e.message || e}`))
    }, 350)
  }, [])

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
        if (list.length) current = await api.getProject(list[0].id)
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
      setPast(items => [...items.slice(-80), clone(current)])
      setFuture([])
    }
    setProjectRef(next)
    scheduleSave(next)
  }, [scheduleSave, setProjectRef])

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
      scheduleSave(current)
    }
  }, [scheduleSave])

  const undo = useCallback(() => {
    const current = projectRef.current
    if (!current || !past.length) return
    const previous = past[past.length - 1]
    setPast(items => items.slice(0, -1))
    setFuture(items => [...items, clone(current)])
    setProjectRef(previous)
    applyLoopFromProject(previous)
    api.saveProject(previous).catch(() => {})
  }, [past, setProjectRef, applyLoopFromProject])

  const redo = useCallback(() => {
    const current = projectRef.current
    if (!current || !future.length) return
    const next = future[future.length - 1]
    setFuture(items => items.slice(0, -1))
    setPast(items => [...items, clone(current)])
    setProjectRef(next)
    applyLoopFromProject(next)
    api.saveProject(next).catch(() => {})
  }, [future, setProjectRef, applyLoopFromProject])


  const openProject = useCallback(async (projectId: string) => {
    try {
      playback.current.sources.forEach(source => { try { source.stop() } catch {} })
      playback.current.sources = []
      cancelAnimationFrame(playback.current.raf)
      setPlaying(false)
      setPlayheadTicks(0)
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

  const stopPlaybackAudio = useCallback(() => {
    playback.current.generation += 1
    playback.current.sources.forEach(source => { try { source.stop() } catch {} })
    playback.current.sources = []
    playback.current.analysers = {}
    playback.current.masterAnalyser = undefined
    // Keep the context alive: decoder and node creation are reused across transport starts.
    playback.current.ctx = undefined
  }, [])

  const getTrackLevel = useCallback((trackId: string) => analyserPeakLevel(playback.current.analysers[trackId]), [])
  const getMasterLevel = useCallback(() => analyserPeakLevel(playback.current.masterAnalyser), [])


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

  const schedulePlayback = useCallback(async (targetProject: Project, startTicks: number, continuous = false) => {
    const generation = playback.current.generation + 1
    playback.current.generation = generation
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
    const ctx = audible.length ? playbackContext() : undefined
    playback.current.ctx = ctx
    playback.current.startMs = performance.now()
    playback.current.startTicks = startTicks
    playback.current.startContextTime = ctx?.currentTime || 0
    if (!audible.length) {
      playback.current.sources = []
      playback.current.analysers = {}
      playback.current.masterAnalyser = undefined
      return true
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
    if (!continuous) {
      playback.current.startMs = performance.now()
      playback.current.startTicks = startTicks
      playback.current.startContextTime = ctx?.currentTime || 0
    }
    const scheduleOffsetSeconds = continuous && ctx
      ? ticksToSeconds(targetProject, playback.current.startTicks) + (ctx.currentTime - playback.current.startContextTime)
      : ticksToSeconds(targetProject, startTicks)
    playback.current.analysers = {}
    const masterInput = ctx.createGain()
    const masterAnalyser = ctx.createAnalyser()
    masterAnalyser.fftSize = 512
    masterInput.connect(masterAnalyser)
    masterAnalyser.connect(ctx.destination)
    playback.current.masterAnalyser = masterAnalyser
    const trackInputs = new Map<string, GainNode>()
    const inputForTrack = (track: Track) => {
      const existing = trackInputs.get(track.id)
      if (existing) return existing
      const input = ctx.createGain()
      const volume = ctx.createGain()
      volume.gain.value = track.volume
      const panner = ctx.createStereoPanner()
      panner.pan.value = track.pan
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 512
      input.connect(volume).connect(panner).connect(analyser)
      analyser.connect(masterInput)
      playback.current.analysers[track.id] = analyser
      trackInputs.set(track.id, input)
      return input
    }
    playback.current.sources = tracksAndBuffers.flatMap(item => {
      if (!item || !ctx) return []
      const source = ctx.createBufferSource()
      source.buffer = item.buffer
      const gain = ctx.createGain()
      const clipGain = Math.pow(10, (item.gainDb || 0) / 20)
      const baseGain = clipGain
      gain.gain.value = baseGain
      source.connect(gain).connect(inputForTrack(item.track))
      const sourceStartSeconds = ticksToSeconds(targetProject, item.sourceStartTicks)
      const sourceOffsetSeconds = secondsBetweenTicks(targetProject, item.sourceStartTicks - item.sourceOffsetTicks, item.sourceStartTicks)
      const clipDurationSeconds = item.sourceDurationTicks
        ? tickDurationSeconds(targetProject, item.sourceStartTicks, item.sourceDurationTicks)
        : Math.max(0, item.buffer.duration - sourceOffsetSeconds)
      const localOffset = scheduleOffsetSeconds - sourceStartSeconds
      const clipStartClock = ctx.currentTime - localOffset
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
      const audibleStartClock = Math.max(ctx.currentTime, clipStartClock + positionNow)
      gain.gain.setValueAtTime(Math.max(0.0001, baseGain * fadeGainAt(positionNow)), audibleStartClock)
      let lastClock = audibleStartClock
      for (const position of Array.from(automationPositions).sort((a, b) => a - b)) {
        if (position <= positionNow + 0.0001 || position > clipDurationSeconds + 0.0001) continue
        const clock = clipStartClock + position
        if (clock <= ctx.currentTime + 0.001 || clock <= lastClock + 0.0005) continue
        gain.gain.linearRampToValueAtTime(Math.max(0.0001, baseGain * fadeGainAt(position)), clock)
        lastClock = clock
      }
      if (localOffset >= 0 && localOffset < clipDurationSeconds) {
        const audioOffset = sourceOffsetSeconds + localOffset
        const remaining = Math.max(0.01, clipDurationSeconds - localOffset)
        source.start(ctx.currentTime, Math.min(Math.max(0, item.buffer.duration - 0.03), audioOffset), remaining)
      } else if (localOffset < 0) {
        source.start(ctx.currentTime - localOffset, sourceOffsetSeconds, Math.max(0.01, clipDurationSeconds))
      }
      return [source]
    })
    return true
  }, [])

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
    playbackRebuildTimer.current = window.setTimeout(() => {
      playbackRebuildTimer.current = null
      void (async () => {
        const current = projectRef.current
        if (!current || !playing) return
        const elapsed = playback.current.ctx ? playback.current.ctx.currentTime - playback.current.startContextTime : (performance.now() - playback.current.startMs) / 1000
        const ticks = secondsToTicks(current, ticksToSeconds(current, playback.current.startTicks) + elapsed)
        stopPlaybackAudio()
        await schedulePlayback(current, ticks, true)
      })()
    }, 120)
  }, [project, playing, schedulePlayback, stopPlaybackAudio])

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
    playbackSnapshotRef.current = playbackAudioSnapshot(project)
    await schedulePlayback(project, playheadTicks)
    playback.current.startMs = performance.now()
    playback.current.startTicks = playheadTicks
    playback.current.startContextTime = playback.current.ctx?.currentTime || 0
    cancelAnimationFrame(playback.current.raf)
    const step = () => {
      const current = projectRef.current
      if (!current) return
      const elapsed = playback.current.ctx ? playback.current.ctx.currentTime - playback.current.startContextTime : (performance.now() - playback.current.startMs) / 1000
      let ticks = secondsToTicks(current, ticksToSeconds(current, playback.current.startTicks) + elapsed)
      const activeLoop = loopEnabledRef.current ? loopRangeRef.current : null
      if (activeLoop && ticks >= activeLoop.end && !loopRestarting.current) {
        loopRestarting.current = true
        const span = Math.max(1, activeLoop.end - activeLoop.start)
        const restartTicks = activeLoop.start + ((ticks - activeLoop.end) % span)
        ticks = restartTicks
        stopPlaybackAudio()
        void schedulePlayback(current, restartTicks).finally(() => { loopRestarting.current = false })
      }
      setPlayheadTicks(Math.floor(ticks))
      playback.current.raf = requestAnimationFrame(step)
    }
    playback.current.raf = requestAnimationFrame(step)
    playback.current.starting = false
    setPlaying(true)
  }, [project, playing, playheadTicks, schedulePlayback, stopPlaybackAudio])

  const stop = useCallback(() => {
    setPlaying(false)
    setPlayheadTicks(0)
    stopPlaybackAudio()
    cancelAnimationFrame(playback.current.raf)
  }, [stopPlaybackAudio])

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') return
      if (event.code === 'Space') { event.preventDefault(); playToggle() }
      if (!event.ctrlKey && !event.metaKey && !event.altKey && event.key.toLowerCase() === 'l') { event.preventDefault(); toggleLoop() }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); undo() }
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
        onTitleChange={title => updateProject(next => { next.title = title }, true)}
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
      />
      <div className="workspace-grid">
        <TrackList
          project={project}
          selectedTrackId={selectedTrack?.id}
          onSelect={setSelectedTrackId}
          onAddTrack={type => updateProject(next => {
            const index = next.tracks.length + 1
            next.tracks.push({
              id: `track_${crypto.randomUUID().slice(0, 12)}`,
              name: type === 'vocal' ? `Vocal ${index}` : `BGM ${index}`,
              type,
              color: type === 'vocal' ? '#7c5cff' : '#2fb996',
              voice_id: 'zero-shot-reference',
              reference_voice_path: null,
              language: 'zh',
              notes: [],
              clips: [],
              automation: { pitch_cents: [], dynamic: [], air: [], falsetto: [], tension: [], energy: [] },
              breaths: [],
              mute: false,
              solo: false,
              volume: 0.8,
              pan: 0,
              render_path: null,
              render_revision: 0,
            })
          }, false)}
          onPatchTrack={patchTrack}
          updateProject={updateProject}
          getTrackLevel={getTrackLevel}
          getMasterLevel={getMasterLevel}
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
          />
        </main>
        <RenderPanel
          project={project}
          track={selectedTrack}
          playheadTicks={playheadTicks}
          jobs={jobs}
          repaintRange={repaintRange}
          onRepaintRange={setRepaintRange}
          onPatchTrack={patchTrack}
          updateProject={updateProject}
          onJobCreated={job => setJobs(current => [job, ...current.filter(j => j.id !== job.id)])}
        />
      </div>
      {error && <div className="error-banner global" onClick={() => setError('')}>{error}</div>}
    </div>
  )
}
