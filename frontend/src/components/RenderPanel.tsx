import { useEffect, useRef, useState } from 'react'
import { api, importAudioClip, renderFileUrl, uploadFile, uploadVoice } from '../api'
import { barTicks, ticksToSeconds } from '../tempo'
import type { MediaFile, Note, Project, RenderJob, Track, VoiceProfile } from '../types'
import { vocalRenderIsStale } from '../renderFingerprint'

interface Props {
  project: Project
  track?: Track
  playheadTicks: number
  jobs: RenderJob[]
  repaintRange: { start: number; end: number }
  onRepaintRange(range: { start: number; end: number }): void
  onPatchTrack(trackId: string, patch: Partial<Track>): void
  onJobCreated(job: RenderJob): void
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
  const [batchLyrics, setBatchLyrics] = useState('')
  const [lyricsError, setLyricsError] = useState('')
  const [lyricScrollTop, setLyricScrollTop] = useState(0)
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
  const staleRender = props.track ? vocalRenderIsStale(props.project, props.track) : false

  async function run(name: string, fn: () => Promise<RenderJob>) {
    setBusy(name); setError('')
    try {
      props.onJobCreated(await fn())
    } catch (e: any) {
      setError(e.message || String(e))
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
    } catch (e: any) { setError(e.message || String(e)) }
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
    } catch (e: any) { setError(e.message || String(e)) }
  }

  async function deleteSelectedVoice() {
    const voice = selectedVoice
    if (!voice || !window.confirm(`Delete reference voice "${voice.name}" and unassign it from projects?`)) return
    setError('')
    try {
      await api.deleteVoice(voice.id, true)
      setVoices(current => current.filter(item => item.id !== voice.id))
    } catch (e: any) { setError(e.message || String(e)) }
  }

  async function uploadSource(file: File) {
    setError('')
    try {
      const result = await uploadFile(file)
      setSourceAudio(result.path)
    } catch (e: any) { setError(e.message || String(e)) }
  }


  const visibleMedia = mediaFiles.filter(item => {
    const query = mediaSearch.trim().toLowerCase()
    return !query || item.name.toLowerCase().includes(query) || item.file_name.toLowerCase().includes(query)
  })

  function readableError(error: unknown): string {
    const raw = error instanceof Error ? error.message : String(error)
    return raw.match(/"detail":"([^"]+)"/)?.[1] || raw.replace(/^\d+: /, '')
  }

  async function placeMedia(item: MediaFile) {
    setError('')
    try {
      await api.placeMediaClip(props.project.id, item.file_name, props.playheadTicks)
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
    } catch (e: any) { setError(e.message || String(e)) }
  }

  const transcribedClips = props.track?.clips.filter(clip => (clip.transcribed_lyrics || []).length) || []
  const selectedVoice = voices.find(voice => voice.id === props.track?.voice_id) || voices.find(voice => voice.path === props.track?.reference_voice_path) || null

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
            <button disabled={!props.track.notes.length || busy === 'vocal'} className="render-button" onClick={() => run('vocal', () => api.renderVocal(props.project.id, props.track!.id))}>
              {busy === 'vocal' ? 'Rendering…' : 'Render vocal'}
            </button>
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
        <div className="path-readout">{sourceAudio ? sourceAudio.split('/').pop() : 'no source selected'}</div>
        <label className="field-label">Style caption
          <textarea value={caption} onChange={e => setCaption(e.target.value)} rows={3} />
        </label>
        <button disabled={!sourceAudio || busy === 'bgm'} className="wide-action" onClick={() => run('bgm', () => api.vocal2bgm(props.project.id, sourceAudio, caption))}>Vocal2BGM</button>
        <p className="hint">Alt-drag on the arrangement timeline to draw the repaint region.</p>
        <div className="repaint-grid">
          <label>Start<input type="number" min="0" step="0.1" value={Number(repaintStart.toFixed(2))} onChange={e => props.onRepaintRange({ start: Number(e.target.value), end: repaintEnd })} /></label>
          <label>End<input type="number" min="0" step="0.1" value={Number(repaintEnd.toFixed(2))} onChange={e => props.onRepaintRange({ start: repaintStart, end: Number(e.target.value) })} /></label>
        </div>
        <button disabled={!sourceAudio || repaintEnd <= repaintStart || busy === 'repaint'} className="wide-action secondary" onClick={() => run('repaint', () => api.repaint(props.project.id, sourceAudio, repaintStart, repaintEnd, caption))}>Repaint selection</button>
        <button disabled={!sourceAudio || busy === 'separate'} className="wide-action secondary" onClick={() => run('separate', () => api.separate(props.project.id, sourceAudio))}>{busy === 'separate' ? 'Separating…' : 'Separate vocal/instrumental'}</button>
        <button disabled={!sourceAudio || !props.track?.reference_voice_path || busy === 'svc'} className="wide-action secondary" onClick={() => run('svc', () => api.svc(props.project.id, sourceAudio, props.track!.reference_voice_path!))}>SVC voice conversion</button>
      </section>

      <section className="side-section media-bin-section">
        <div className="panel-title">Media bin</div>
        <input className="media-search" placeholder="Search uploaded audio" value={mediaSearch} onChange={event => setMediaSearch(event.target.value)} />
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
                {url && <audio controls preload="none" src={url} />}
                <div className="media-actions">
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
            <div className="job-row"><strong>{job.mode}{job.fixture ? ' · CI FIXTURE' : ''}</strong><span>{job.status}</span></div>
            <div className="progress"><div style={{ width: `${Math.round(job.progress * 100)}%` }} /></div>
            <div className="job-message">{job.error || job.message}</div>
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
          {['wav', 'mp4', 'mid', 'lrc', 'ustx', 'svp', 'vpr'].map(fmt => (
            <a key={fmt} className="export-button" href={api.exportUrl(props.project.id, fmt)}>{fmt.toUpperCase()}</a>
          ))}
        </div>
      </section>
      {error && <div className="error-banner">{error}</div>}
    </aside>
  )
}
