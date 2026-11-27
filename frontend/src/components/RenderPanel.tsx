import { useEffect, useRef, useState } from 'react'
import { api, renderFileUrl, uploadFile, uploadVoice } from '../api'
import type { Project, RenderJob, Track, VoiceProfile } from '../types'

interface Props {
  project: Project
  track?: Track
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
  const referenceInput = useRef<HTMLInputElement | null>(null)
  const audioInput = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    const refresh = () => api.listVoices().then(setVoices).catch(() => {})
    refresh()
    const events = new EventSource('/api/events')
    events.addEventListener('voice_library', refresh)
    return () => events.close()
  }, [])

  const activeJobs = props.jobs.filter(j => j.project_id === props.project.id).slice(0, 8)
  const latestDiagnostic = activeJobs.find(j => j.diagnostic_path)?.diagnostic_path

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
            <button disabled={!props.track.notes.length || busy === 'vocal'} className="render-button" onClick={() => run('vocal', () => api.renderVocal(props.project.id, props.track!.id))}>
              {busy === 'vocal' ? 'Rendering…' : 'Render vocal'}
            </button>
          </>
        ) : <div className="empty-state">Select a track</div>}
      </section>

      <section className="side-section">
        <div className="panel-title">ACE-Step music</div>
        <input ref={audioInput} hidden type="file" accept="audio/*" onChange={e => e.target.files?.[0] && uploadSource(e.target.files[0])} />
        <button className="wide-button" onClick={() => audioInput.current?.click()}>Upload vocal/audio source</button>
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
