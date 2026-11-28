import { useEffect, useRef, useState } from 'react'
import { api, importAudioClip, renderFileUrl, uploadFile, uploadVoice, voiceAudioUrl } from '../api'
import { barTicks, tickDurationSeconds, ticksToSeconds } from '../tempo'
import type { MediaFile, Note, Project, RenderJob, Track, VoiceProfile } from '../types'
import { vocalRenderInputHash, vocalRenderIsStale } from '../renderFingerprint'

interface Props {
  project: Project
  track?: Track
  playheadTicks: number
  jobs: RenderJob[]
  repaintRange: { start: number; end: number }
  onRepaintRange(range: { start: number; end: number }): void
  onPatchTrack(trackId: string, patch: Partial<Track>): void
  updateProject(mutator: (project: Project) => void, transient?: boolean): void
  onJobCreated(job: RenderJob): void
}

function sourceClipForPath(project: Project, path: string, playheadTicks: number) {
  if (!path) return null
  const matches = project.tracks.flatMap(track => track.clips).filter(clip => clip.path === path)
  if (!matches.length) return null
  return matches.find(clip => clip.duration_ticks && playheadTicks >= clip.start_ticks && playheadTicks < clip.start_ticks + clip.duration_ticks) || matches[0]
}

function overlappingRepaintClip(project: Project, startS: number, endS: number, preferredPath: string) {
  let best: { clip: import('../types').AudioClip; overlap: number; pathMatch: boolean } | null = null
  for (const track of project.tracks) {
    if (track.type !== 'accompaniment') continue
    for (const clip of track.clips) {
      if (!clip.duration_ticks) continue
      const clipStart = ticksToSeconds(project, clip.start_ticks)
      const clipEnd = clipStart + tickDurationSeconds(project, clip.start_ticks, clip.duration_ticks)
      const overlap = Math.min(endS, clipEnd) - Math.max(startS, clipStart)
      if (overlap <= 0) continue
      const pathMatch = Boolean(preferredPath) && clip.path === preferredPath
      if (!best || (pathMatch && !best.pathMatch) || (pathMatch === best.pathMatch && overlap > best.overlap)) {
        best = { clip, overlap, pathMatch }
      }
    }
  }
  return best?.clip || null
}

export default function RenderPanel(props: Props) {
  const [sourceAudio, setSourceAudio] = useState('')
  const [caption, setCaption] = useState('lush modern pop accompaniment, tight drums, warm bass, cinematic polish')
  const repaintStart = props.repaintRange.start
  const repaintEnd = props.repaintRange.end
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [voices, setVoices] = useState<VoiceProfile[]>([])
  const [mediaFiles, setMediaFiles] = useState<MediaFile[]>([])
  const [mediaSearch, setMediaSearch] = useState('')
  const [mediaFolderFilter, setMediaFolderFilter] = useState('')
  const [batchLyrics, setBatchLyrics] = useState('')
  const [trimStart, setTrimStart] = useState(0)
  const [trimEnd, setTrimEnd] = useState(0)
  const [lyricsError, setLyricsError] = useState('')
  const [lyricScrollTop, setLyricScrollTop] = useState(0)
  const [clockNow, setClockNow] = useState(() => Date.now())
  const [autoRender, setAutoRender] = useState(() => window.localStorage.getItem('openace.autoRender') === '1')
  const autoRenderAttempts = useRef<Record<string, string>>({})
  const referenceInput = useRef<HTMLInputElement | null>(null)
  const lyricListRef = useRef<HTMLDivElement | null>(null)
  const audioInput = useRef<HTMLInputElement | null>(null)
  const clipInput = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    const refresh = () => {
      api.listVoices().then(setVoices).catch(() => {})
      api.listMedia().then(setMediaFiles).catch(() => {})
    }
    refresh()
    const events = new EventSource('/api/events')
    events.addEventListener('voice_library', refresh)
    events.addEventListener('media_library', refresh)
    return () => events.close()
  }, [])

  const activeJobs = props.jobs.filter(j => j.project_id === props.project.id).slice(0, 8)
  const latestDiagnostic = activeJobs.find(j => j.diagnostic_path)?.diagnostic_path
  const hasActiveJobs = activeJobs.some(job => job.status === 'queued' || job.status === 'running')
  const queuedPositions = new Map(activeJobs.filter(job => job.status === 'queued').map((job, index) => [job.id, index + 1]))

  useEffect(() => {
    if (!hasActiveJobs) return
    const timer = window.setInterval(() => setClockNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [hasActiveJobs])

  function jobTiming(job: RenderJob) {
    const end = job.finished_at || clockNow / 1000
    const seconds = Math.max(0, end - job.created_at)
    const formatted = seconds < 10 ? seconds.toFixed(1) : Math.round(seconds).toString()
    if (job.status === 'queued') return `queued ${formatted}s · FIFO #${queuedPositions.get(job.id) || 1}`
    if (job.status === 'running') return `${formatted}s elapsed`
    return `${formatted}s total`
  }
  const staleRender = props.track ? vocalRenderIsStale(props.project, props.track) : false
  const repaintClip = overlappingRepaintClip(props.project, repaintStart, repaintEnd, sourceAudio)
  const selectedVocalRender = props.track?.type === 'vocal' ? (props.track.render_path || '') : ''
  const usesSelectedVocalRender = !sourceAudio && Boolean(selectedVocalRender)
  const effectiveSourceAudio = sourceAudio || selectedVocalRender
  const vocal2bgmClip = sourceAudio ? sourceClipForPath(props.project, sourceAudio, props.playheadTicks) : null

  useEffect(() => {
    window.localStorage.setItem('openace.autoRender', autoRender ? '1' : '0')
  }, [autoRender])

  useEffect(() => {
    if (!autoRender) return
    const timer = window.setTimeout(() => {
      void (async () => {
        for (const track of props.project.tracks) {
          if (track.type !== 'vocal' || !track.notes.length) continue
          const fingerprint = vocalRenderInputHash(props.project, track)
          const stale = !track.render_path || vocalRenderIsStale(props.project, track)
          if (!stale) {
            delete autoRenderAttempts.current[track.id]
            continue
          }
          const active = props.jobs.some(job => job.project_id === props.project.id && job.track_id === track.id && job.mode === 'svs_score' && (job.status === 'queued' || job.status === 'running'))
          if (active || autoRenderAttempts.current[track.id] === fingerprint) continue
          autoRenderAttempts.current[track.id] = fingerprint
          try {
            props.onJobCreated(await api.renderVocal(props.project.id, track.id))
          } catch (error: any) {
            setError(`Auto render: ${readableError(error)}`)
          }
        }
      })()
    }, 1500)
    return () => window.clearTimeout(timer)
  }, [autoRender, props.project, props.jobs])

  function renderVocalManually() {
    if (!props.track) return
    autoRenderAttempts.current[props.track.id] = vocalRenderInputHash(props.project, props.track)
    void run('vocal', () => api.renderVocal(props.project.id, props.track!.id))
  }

  async function run(name: string, fn: () => Promise<RenderJob>) {
    setBusy(name); setError('')
    try {
      props.onJobCreated(await fn())
    } catch (e: any) {
      setError(readableError(e))
    } finally {
      setBusy(null)
    }
  }


  function transposeNotes(semitones: number) {
    if (!props.track?.notes.length) return
    props.onPatchTrack(props.track.id, {
      notes: props.track.notes.map(note => ({ ...note, pitch: note.pitch + semitones })),
    })
  }

  async function uploadReference(file: File) {
    if (!props.track) return
    setError('')
    try {
      const voice = await uploadVoice(file)
      setVoices(current => [voice, ...current])
      props.onPatchTrack(props.track.id, { reference_voice_path: voice.path, voice_id: voice.id })
    } catch (e: any) { setError(readableError(e)) }
  }

  function assignVoice(voiceId: string) {
    if (!props.track) return
    const voice = voices.find(item => item.id === voiceId)
    props.onPatchTrack(props.track.id, {
      reference_voice_path: voice?.path || null,
      voice_id: voice?.id || '',
    })
  }

  async function renameSelectedVoice() {
    const voice = selectedVoice
    if (!voice) return
    const name = window.prompt('Rename reference voice', voice.name)?.trim()
    if (!name) return
    setError('')
    try {
      const updated = await api.renameVoice(voice.id, name)
      setVoices(current => current.map(item => item.id === updated.id ? updated : item))
    } catch (e: any) { setError(readableError(e)) }
  }

  async function trimSelectedVoice() {
    const voice = selectedVoice
    if (!voice || !props.track) return
    setError('')
    try {
      const trimmed = await api.trimVoice(voice.id, trimStart, trimEnd)
      setVoices(current => [trimmed, ...current.filter(item => item.id !== trimmed.id)])
      props.onPatchTrack(props.track.id, { reference_voice_path: trimmed.path, voice_id: trimmed.id })
    } catch (e: any) { setError(readableError(e)) }
  }

  async function deleteSelectedVoice() {
    const voice = selectedVoice
    if (!voice || !window.confirm(`Delete reference voice "${voice.name}" and unassign it from projects?`)) return
    setError('')
    try {
      await api.deleteVoice(voice.id, true)
      setVoices(current => current.filter(item => item.id !== voice.id))
    } catch (e: any) { setError(readableError(e)) }
  }

  async function uploadSource(file: File) {
    setError('')
    try {
      const result = await uploadFile(file)
      setSourceAudio(result.path)
    } catch (e: any) { setError(readableError(e)) }
  }


  const mediaFolders = Array.from(new Set(mediaFiles.flatMap(item => item.folders || []))).sort((a, b) => a.localeCompare(b))
  const visibleMedia = mediaFiles.filter(item => {
    const query = mediaSearch.trim().toLowerCase()
    const matchesFolder = !mediaFolderFilter || (item.folders || []).includes(mediaFolderFilter)
    return matchesFolder && (!query || item.name.toLowerCase().includes(query) || item.file_name.toLowerCase().includes(query) || (item.tags || []).some(tag => tag.toLowerCase().includes(query)) || (item.folders || []).some(folder => folder.toLowerCase().includes(query)))
  })

  async function editMediaOrganization(item: MediaFile) {
    const tags = window.prompt('Comma-separated media tags', (item.tags || []).join(', '))
    if (tags === null) return
    const folders = window.prompt('Comma-separated media folders', (item.folders || []).join(', '))
    if (folders === null) return
    setError('')
    try {
      const updated = await api.updateMediaOrganization(item.file_name, {
        tags: tags.split(',').map(value => value.trim()).filter(Boolean),
        folders: folders.split(',').map(value => value.trim()).filter(Boolean),
      })
      setMediaFiles(current => current.map(candidate => candidate.file_name === item.file_name ? updated : candidate))
    } catch (e: any) { setError(readableError(e)) }
  }

  function readableError(error: unknown): string {
    const raw = error instanceof Error ? error.message : String(error)
    return raw.match(/"detail":"([^"]+)"/)?.[1] || raw.replace(/^\d+: /, '')
  }

  async function placeMedia(item: MediaFile) {
    setError('')
    try {
      await api.placeMediaClip(props.project.id, item.file_name, props.playheadTicks, props.track?.type !== 'vocal' ? props.track?.id : undefined)
    } catch (e: any) { setError(readableError(e)) }
  }

  async function cancelRenderJob(job: RenderJob) {
    setError('')
    try {
      await api.cancelJob(job.id)
    } catch (e: any) { setError(readableError(e)) }
  }

  async function deleteMedia(item: MediaFile) {
    if (!window.confirm(`Delete media file "${item.name}"?`)) return
    setError('')
    try {
      await api.deleteMedia(item.file_name)
      setMediaFiles(current => current.filter(candidate => candidate.file_name !== item.file_name))
    } catch (e: any) { setError(readableError(e)) }
  }

  const sortedNotes = props.track?.type === 'vocal' ? [...props.track.notes].sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch) : []
  const missingLyrics = sortedNotes.filter(note => !note.lyric.trim()).length
  const lyricRowHeight = 34
  const lyricViewportHeight = 220
  const lyricStart = Math.max(0, Math.floor(lyricScrollTop / lyricRowHeight) - 4)
  const lyricEnd = Math.min(sortedNotes.length, lyricStart + Math.ceil(lyricViewportHeight / lyricRowHeight) + 8)
  const visibleLyricNotes = sortedNotes.slice(lyricStart, lyricEnd)

  useEffect(() => {
    setLyricScrollTop(0)
    if (lyricListRef.current) lyricListRef.current.scrollTop = 0
  }, [props.project.id, props.track?.id, sortedNotes.length])

  function lyricTokens(text: string): string[] {
    return text.trim().split(/\s+/).filter(Boolean).flatMap(chunk => {
      // Continuous CJK input is one syllable per character; whitespace can still be
      // used to force a multi-character word/romanized syllable onto one note.
      return /[\u3400-\u9fff\uf900-\ufaff]/.test(chunk) ? Array.from(chunk) : [chunk]
    })
  }

  function commitLyric(note: Note, value: string) {
    if (!props.track || value.trim() === note.lyric) return
    const noteId = note.id
    const lyric = value.trim()
    props.onPatchTrack(props.track.id, {
      notes: props.track.notes.map(item => item.id === noteId ? { ...item, lyric, phonemes: [] } : item),
    })
    setLyricsError('')
  }

  function applyBatchLyrics() {
    if (!props.track) return
    const tokens = lyricTokens(batchLyrics)
    if (!tokens.length) {
      setLyricsError('Paste lyrics before applying batch correction.')
      return
    }
    if (tokens.length !== sortedNotes.length) {
      setLyricsError(`Lyric token count ${tokens.length} does not match note count ${sortedNotes.length}; nothing was changed.`)
      return
    }
    const trackId = props.track.id
    props.onPatchTrack(trackId, {
      notes: props.track.notes.map(note => {
        const index = sortedNotes.findIndex(item => item.id === note.id)
        return index >= 0 ? { ...note, lyric: tokens[index], phonemes: [] } : note
      }),
    })
    setBatchLyrics('')
    setLyricsError('')
  }

  function updateClipLyric(clipId: string, index: number, patch: Partial<{ text: string; start: number; end: number }>) {
    if (!props.track) return
    const trackId = props.track.id
    let invalid = ''
    const clips = props.track.clips.map(clip => {
      if (clip.id !== clipId) return clip
      const words = (clip.transcribed_lyrics || []).map((word, wordIndex) => {
        if (wordIndex !== index) return word
        const next = { ...word, ...patch }
        if (!next.text.trim()) invalid = 'Lyric text cannot be empty.'
        if (!(next.end > next.start)) invalid = 'Lyric end must be after its start.'
        return next
      })
      return { ...clip, transcribed_lyrics: words }
    })
    if (invalid) {
      setLyricsError(invalid)
      return
    }
    props.onPatchTrack(trackId, { clips })
    setLyricsError('')
  }

  function deleteClipLyric(clipId: string, index: number) {
    if (!props.track) return
    props.onPatchTrack(props.track.id, {
      clips: props.track.clips.map(clip => clip.id === clipId ? {
        ...clip,
        transcribed_lyrics: (clip.transcribed_lyrics || []).filter((_word, wordIndex) => wordIndex !== index),
      } : clip),
    })
  }

  function addClipLyric(clipId: string, index: number) {
    if (!props.track) return
    props.onPatchTrack(props.track.id, {
      clips: props.track.clips.map(clip => {
        if (clip.id !== clipId) return clip
        const words = [...(clip.transcribed_lyrics || [])]
        const anchor = words[index]
        const text = window.prompt('New lyric word')?.trim()
        if (!text) return clip
        const start = anchor ? anchor.end + 0.02 : 0
        words.splice(index + 1, 0, { text, start, end: start + 0.3 })
        return { ...clip, transcribed_lyrics: words }
      }),
    })
  }

  async function importClipFile(file: File) {
    setError('')
    try {
      const targetTrackId = props.track && props.track.type !== 'vocal' ? props.track.id : undefined
      await importAudioClip(props.project.id, file, props.playheadTicks, targetTrackId)
    } catch (e: any) { setError(readableError(e)) }
  }

  const transcribedClips = props.track?.clips.filter(clip => (clip.transcribed_lyrics || []).length) || []
  const selectedVoice = voices.find(voice => voice.id === props.track?.voice_id) || voices.find(voice => voice.path === props.track?.reference_voice_path) || null

  useEffect(() => {
    setTrimStart(0)
    setTrimEnd(selectedVoice?.duration_seconds || 0)
  }, [selectedVoice?.id, selectedVoice?.duration_seconds])

  const karaokeStyle = {
    font_size: 66,
    lane_spacing: 76,
    sung_color: '#ffb000',
    unsung_color: '#d9d9d9',
    background_theme: 'midnight',
    background_motion: true,
    show_title: true,
    show_brand: true,
    ...((props.project.metadata?.karaoke_style && typeof props.project.metadata.karaoke_style === 'object') ? props.project.metadata.karaoke_style : {}),
  }

  function updateKaraokeStyle(patch: Record<string, unknown>) {
    props.updateProject(project => {
      project.metadata = { ...(project.metadata || {}) }
      project.metadata.karaoke_style = { ...karaokeStyle, ...patch }
    }, false)
  }

  return (
    <aside className="right-panel">
      <section className="side-section">
        <div className="panel-title">Voice</div>
        {props.track ? (
          <>
            <div className="voice-card">
              <div className="voice-avatar">{(selectedVoice?.name || props.track.name).slice(0, 1).toUpperCase()}</div>
              <div>
                <div className="voice-name">{selectedVoice?.name || 'Zero-shot reference slot'}</div>
                <div className="voice-sub">{selectedVoice ? `${selectedVoice.duration_seconds.toFixed(1)}s · ${(selectedVoice.sample_rate / 1000).toFixed(1)}kHz` : props.track.reference_voice_path ? 'project-local reference loaded' : 'no reference assigned'}</div>
              </div>
            </div>
            <select className="voice-select" value={selectedVoice?.id || ''} onChange={event => assignVoice(event.target.value)}>
              <option value="">No reference assigned</option>
              {voices.map(voice => <option key={voice.id} value={voice.id}>{voice.name} · {voice.duration_seconds.toFixed(1)}s</option>)}
            </select>
            <input ref={referenceInput} hidden type="file" accept="audio/*" onChange={e => { const file = e.target.files?.[0]; if (file) uploadReference(file); e.target.value = '' }} />
            {selectedVoice && (
              <div className="voice-quality">
                <audio controls preload="none" src={voiceAudioUrl(selectedVoice.id) || undefined} />
                <div className="voice-metrics">
                  peak {selectedVoice.peak_level.toFixed(2)} · RMS {selectedVoice.rms_dbfs.toFixed(1)}dB · voiced {selectedVoice.voiced_seconds.toFixed(1)}s
                </div>
                {selectedVoice.quality_warnings.map((warning, index) => <div key={index} className="voice-warning">{warning}</div>)}
                <div className="voice-trim-row">
                  <label>start<input type="number" min="0" max={selectedVoice.duration_seconds} step="0.05" value={trimStart} onChange={event => setTrimStart(Number(event.target.value))} /></label>
                  <label>end<input type="number" min="0" max={selectedVoice.duration_seconds} step="0.05" value={trimEnd} onChange={event => setTrimEnd(Number(event.target.value))} /></label>
                  <button disabled={trimEnd <= trimStart || trimEnd - trimStart <= 0.05} onClick={trimSelectedVoice}>Trim copy</button>
                </div>
                {selectedVoice.source_voice_id && <div className="voice-metrics">trimmed copy {selectedVoice.trim_start_seconds?.toFixed(2)}–{selectedVoice.trim_end_seconds?.toFixed(2)}s; original preserved</div>}
              </div>
            )}
            <div className="voice-actions">
              <button onClick={() => referenceInput.current?.click()}>Upload</button>
              <button disabled={!selectedVoice} onClick={renameSelectedVoice}>Rename</button>
              <button disabled={!selectedVoice} onClick={deleteSelectedVoice}>Delete</button>
            </div>
            <label className="field-label">Language
              <select value={props.track.language} onChange={e => props.onPatchTrack(props.track!.id, { language: e.target.value })}>
                <option value="zh">Mandarin</option><option value="en">English</option><option value="yue">Cantonese</option>
              </select>
            </label>
            <div className="transpose-row">
              <span>Transpose</span>
              <button onClick={() => transposeNotes(-12)}>-12</button>
              <button onClick={() => transposeNotes(-1)}>-1</button>
              <button onClick={() => transposeNotes(1)}>+1</button>
              <button onClick={() => transposeNotes(12)}>+12</button>
            </div>
            {staleRender && <div className="stale-render-warning">Rendered audio is older than the current notes, expression, tempo, or voice. Playback/export still use the old render until you render again.</div>}
            <button disabled={!props.track.notes.length || busy === 'vocal'} className="render-button" onClick={renderVocalManually}>
              {busy === 'vocal' ? 'Rendering…' : 'Render vocal'}
            </button>
            <label className="auto-render-toggle" title="After edits settle for 1.5 seconds, queue stale or never-rendered vocal tracks through the normal FIFO render queue. Cancelled/failed jobs are not retried until the musical input changes.">
              <input type="checkbox" checked={autoRender} onChange={event => setAutoRender(event.target.checked)} />
              Auto render edits
            </label>
          </>
        ) : <div className="empty-state">Select a track</div>}
      </section>

      <section className="side-section lyric-correction-section">
        <div className="panel-title">Lyric correction</div>
        {props.track?.type === 'vocal' && sortedNotes.length ? (
          <>
            <div className="lyric-summary"><strong>{sortedNotes.length}</strong> notes · <strong>{missingLyrics}</strong> missing lyrics</div>
            <textarea
              className="batch-lyrics-input"
              rows={2}
              value={batchLyrics}
              placeholder="Paste lyrics: continuous Chinese maps one character per note; use spaces for multi-letter syllables"
              onChange={event => setBatchLyrics(event.target.value)}
            />
            <button className="wide-action secondary" onClick={applyBatchLyrics}>Apply batch lyrics</button>
            {lyricsError && <div className="inline-error">{lyricsError}</div>}
            <div ref={lyricListRef} className="lyric-correction-list" onScroll={event => setLyricScrollTop((event.target as HTMLDivElement).scrollTop)}>
              <div style={{ height: sortedNotes.length * lyricRowHeight, position: 'relative' }}>
                <div className="lyric-correction-window" style={{ transform: `translateY(${lyricStart * lyricRowHeight}px)` }}>
                  {visibleLyricNotes.map((note, visibleIndex) => {
                    const index = lyricStart + visibleIndex
                    const bar = Math.floor(note.start_ticks / barTicks(props.project)) + 1
                    return (
                      <div key={`${note.id}:${note.lyric}`} className={`lyric-correction-row ${note.lyric.trim() ? '' : 'missing'}`}>
                        <span className="lyric-index">{index + 1}</span>
                        <span className="lyric-position" title={`${ticksToSeconds(props.project, note.start_ticks).toFixed(2)}s`}>{bar} · {note.pitch}</span>
                        <input
                          defaultValue={note.lyric}
                          placeholder="missing"
                          onBlur={event => commitLyric(note, event.target.value)}
                          onKeyDown={event => { if (event.key === 'Enter') (event.target as HTMLInputElement).blur() }}
                        />
                        <span className="lyric-phonemes">{note.phonemes.map(item => item.symbol).join(' ')}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </>
        ) : <div className="empty-state">Select a vocal track with notes</div>}
      </section>

      {transcribedClips.length > 0 && (
        <section className="side-section clip-lyrics-section">
          <div className="panel-title">SVC clip lyrics</div>
          {transcribedClips.map(clip => (
            <div className="clip-lyrics-card" key={clip.id}>
              <div className="lyric-summary"><strong>{clip.transcribed_lyrics!.length}</strong> ASR words · {clip.label || 'audio clip'}</div>
              {lyricsError && <div className="inline-error">{lyricsError}</div>}
              <div className="clip-lyrics-list">
                {clip.transcribed_lyrics!.map((word, index) => (
                  <div className="clip-lyric-row" key={`${clip.id}:${index}:${word.text}:${word.start}:${word.end}`}>
                    <input className="clip-lyric-text" defaultValue={word.text} onBlur={event => updateClipLyric(clip.id, index, { text: event.target.value.trim() })} onKeyDown={event => { if (event.key === 'Enter') (event.target as HTMLInputElement).blur() }} />
                    <input className="clip-lyric-time" type="number" step="0.01" min="0" defaultValue={word.start} onBlur={event => updateClipLyric(clip.id, index, { start: Number(event.target.value) })} />
                    <input className="clip-lyric-time" type="number" step="0.01" min="0" defaultValue={word.end} onBlur={event => updateClipLyric(clip.id, index, { end: Number(event.target.value) })} />
                    <button title="Add word after" onClick={() => addClipLyric(clip.id, index)}>+</button>
                    <button title="Delete word" onClick={() => deleteClipLyric(clip.id, index)}>×</button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </section>
      )}

      <section className="side-section">
        <div className="panel-title">ACE-Step music</div>
        <input ref={audioInput} hidden type="file" accept="audio/*" onChange={e => e.target.files?.[0] && uploadSource(e.target.files[0])} />
        <button className="wide-button" onClick={() => audioInput.current?.click()}>Upload vocal/audio source</button>
        <input ref={clipInput} hidden type="file" accept="audio/*,.wav,.mp3,.flac,.ogg,.aiff,.aif" onChange={e => { const file = e.target.files?.[0]; if (file) void importClipFile(file); e.target.value = '' }} />
        <button className="wide-action secondary" onClick={() => clipInput.current?.click()}>Import audio as clip at playhead</button>
        <div className="path-readout">{sourceAudio ? sourceAudio.split('/').pop() : (usesSelectedVocalRender ? 'selected vocal render' : 'no source selected')}</div>
        <label className="field-label">Style caption
          <textarea value={caption} onChange={e => setCaption(e.target.value)} rows={3} />
        </label>
        <button disabled={!effectiveSourceAudio || (usesSelectedVocalRender && staleRender) || busy === 'bgm'} className="wide-action" title={usesSelectedVocalRender && staleRender ? 'Selected vocal render is stale; render it first' : usesSelectedVocalRender ? 'Use the selected vocal track render as input' : (vocal2bgmClip ? 'Use the matching arrangement clip segment as input' : 'Use the uploaded source file as input')} onClick={() => run('bgm', () => api.vocal2bgm(props.project.id, effectiveSourceAudio, caption, usesSelectedVocalRender ? props.track?.id : undefined, vocal2bgmClip?.id))}>Vocal2BGM</button>
        {usesSelectedVocalRender && <div className="hint vocal2bgm-source">input: selected vocal render</div>}
        {vocal2bgmClip && <div className="hint vocal2bgm-source">input: visible clip segment · aligned to clip start</div>}
        <p className="hint">Alt-drag on the arrangement timeline to draw the repaint region.</p>
        <div className="repaint-grid">
          <label>Start<input type="number" min="0" step="0.1" value={Number(repaintStart.toFixed(2))} onChange={e => props.onRepaintRange({ start: Number(e.target.value), end: repaintEnd })} /></label>
          <label>End<input type="number" min="0" step="0.1" value={Number(repaintEnd.toFixed(2))} onChange={e => props.onRepaintRange({ start: repaintStart, end: Number(e.target.value) })} /></label>
        </div>
        <button disabled={!repaintClip || repaintEnd <= repaintStart || busy === 'repaint'} className="wide-action secondary" title={repaintClip ? `Repaint ${repaintClip.label || repaintClip.path.split('/').pop()} using source-file timing` : 'Draw a region overlapping an accompaniment clip'} onClick={() => repaintClip && run('repaint', () => api.repaint(props.project.id, repaintClip.path, repaintStart, repaintEnd, caption, repaintClip.id))}>Repaint selection</button>
        {repaintClip && <div className="hint repaint-target">target: {repaintClip.label || repaintClip.path.split('/').pop()}</div>}
        <button disabled={!sourceAudio || busy === 'separate'} className="wide-action secondary" onClick={() => run('separate', () => api.separate(props.project.id, sourceAudio))}>{busy === 'separate' ? 'Separating…' : 'Separate vocal/instrumental'}</button>
        <button disabled={!sourceAudio || !props.track?.reference_voice_path || busy === 'svc'} className="wide-action secondary" onClick={() => run('svc', () => api.svc(props.project.id, sourceAudio, props.track!.reference_voice_path!))}>SVC voice conversion</button>
      </section>

      <section className="side-section media-bin-section">
        <div className="panel-title">Media bin</div>
        <div className="media-filter-row"><input className="media-search" placeholder="Search uploaded audio" value={mediaSearch} onChange={event => setMediaSearch(event.target.value)} /><select value={mediaFolderFilter} onChange={event => setMediaFolderFilter(event.target.value)} title="Filter media folder"><option value="">All folders</option>{mediaFolders.map(folder => <option key={folder} value={folder}>{folder}</option>)}</select></div>
        {!visibleMedia.length && <div className="empty-state">No uploaded audio</div>}
        <div className="media-list">
          {visibleMedia.map(item => {
            const url = renderFileUrl(item.path)
            return (
              <div
                className={`media-row ${item.valid ? '' : 'invalid'}`}
                key={item.file_name}
                draggable={item.valid}
                onDragStart={event => {
                  event.dataTransfer.setData('application/x-openace-media', item.file_name)
                  event.dataTransfer.effectAllowed = 'copy'
                }}
              >
                <div className="media-row-head">
                  <strong title={item.file_name}>{item.name}</strong>
                  <span>{item.valid ? `${(item.duration_seconds || 0).toFixed(2)}s · ${Math.round((item.sample_rate || 0) / 100) / 10}k` : 'invalid'}</span>
                </div>
                {(!!item.tags?.length || !!item.folders?.length) && <div className="media-labels">{(item.folders || []).map(folder => <span key={`f${folder}`} className="media-folder">▸{folder}</span>)}{(item.tags || []).map(tag => <span key={`t${tag}`} className="media-tag">#{tag}</span>)}</div>}
                {url && <audio controls preload="none" src={url} />}
                <div className="media-actions">
                  <button onClick={() => void editMediaOrganization(item)}>Tags</button>
                  <button disabled={!item.valid} onClick={() => void placeMedia(item)}>Add at playhead</button>
                  <button className="danger" onClick={() => void deleteMedia(item)}>Delete</button>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <section className="side-section jobs-section">
        <div className="panel-title">Render jobs</div>
        {activeJobs.length === 0 && <div className="empty-state">No renders yet</div>}
        {activeJobs.map(job => (
          <div key={job.id} className={`job-card ${job.status}`}>
            <div className="job-row"><strong>{job.mode}{job.fixture ? ' · CI FIXTURE' : ''}</strong><span>{job.status} · {Math.round(job.progress * 100)}%</span></div>
            <div className="progress"><div style={{ width: `${Math.round(job.progress * 100)}%` }} /></div>
            <div className="job-message">{job.error || job.message}</div>
            <div className="job-timing">{jobTiming(job)}</div>
            {(job.status === 'queued' || job.status === 'running') && <button className="job-cancel danger" onClick={() => void cancelRenderJob(job)}>{job.status === 'queued' ? 'Cancel queued job' : 'Cancel running job'}</button>}
            {job.output_path && renderFileUrl(job.output_path) && <audio controls src={renderFileUrl(job.output_path)!} />}
          </div>
        ))}
      </section>

      {latestDiagnostic && renderFileUrl(latestDiagnostic) && (
        <section className="side-section">
          <div className="panel-title">Acoustic X-ray</div>
          <img className="diagnostic-image" src={renderFileUrl(latestDiagnostic)!} alt="diagnostic" />
        </section>
      )}

      <section className="side-section">
        <div className="panel-title">Export</div>
        <div className="export-grid">
          {['wav', 'mp3', 'flac', 'ogg', 'stems', 'mp4', 'mid', 'lrc', 'ustx', 'svp', 'vpr'].map(fmt => (
            <a key={fmt} className="export-button" href={api.exportUrl(props.project.id, fmt)}>{fmt.toUpperCase()}</a>
          ))}
        </div>
        <div className="karaoke-style-editor">
          <div className="panel-subtitle">Karaoke video style</div>
          <label>Font size<input type="number" min="36" max="96" value={karaokeStyle.font_size} onChange={event => updateKaraokeStyle({ font_size: Number(event.target.value) })} /></label>
          <label>Lane spacing<input type="number" min="52" max="112" value={karaokeStyle.lane_spacing} onChange={event => updateKaraokeStyle({ lane_spacing: Number(event.target.value) })} /></label>
          <label>Sung<input type="color" value={karaokeStyle.sung_color} onChange={event => updateKaraokeStyle({ sung_color: event.target.value })} /></label>
          <label>Unsung<input type="color" value={karaokeStyle.unsung_color} onChange={event => updateKaraokeStyle({ unsung_color: event.target.value })} /></label>
          <label>Theme<select value={karaokeStyle.background_theme} onChange={event => updateKaraokeStyle({ background_theme: event.target.value })}>
            <option value="midnight">Midnight</option>
            <option value="ember">Ember</option>
            <option value="forest">Forest</option>
            <option value="monochrome">Monochrome</option>
          </select></label>
          <label className="check-row"><input type="checkbox" checked={karaokeStyle.background_motion} onChange={event => updateKaraokeStyle({ background_motion: event.target.checked })} /> Motion</label>
          <label className="check-row"><input type="checkbox" checked={karaokeStyle.show_title} onChange={event => updateKaraokeStyle({ show_title: event.target.checked })} /> Title</label>
          <label className="check-row"><input type="checkbox" checked={karaokeStyle.show_brand} onChange={event => updateKaraokeStyle({ show_brand: event.target.checked })} /> Brand</label>
        </div>
      </section>
      {error && <div className="error-banner">{error}</div>}
    </aside>
  )
}
