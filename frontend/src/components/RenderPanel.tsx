import { useEffect, useRef, useState } from 'react'
import { api, renderFileUrl, uploadFile } from '../api'
import type { Project, RenderJob, Track } from '../types'

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
  const referenceInput = useRef<HTMLInputElement | null>(null)
  const audioInput = useRef<HTMLInputElement | null>(null)

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
      const result = await uploadFile(file)
      props.onPatchTrack(props.track.id, { reference_voice_path: result.path })
    } catch (e: any) { setError(e.message || String(e)) }
  }

  async function uploadSource(file: File) {
    setError('')
    try {
      const result = await uploadFile(file)
      setSourceAudio(result.path)
    } catch (e: any) { setError(e.message || String(e)) }
  }

  return (
    <aside className="right-panel">
      <section className="side-section">
        <div className="panel-title">Voice</div>
        {props.track ? (
          <>
            <div className="voice-card">
              <div className="voice-avatar">{props.track.name.slice(0, 1).toUpperCase()}</div>
              <div>
                <div className="voice-name">Zero-shot reference slot</div>
                <div className="voice-sub">{props.track.reference_voice_path ? 'custom reference loaded' : 'no reference uploaded'}</div>
              </div>
            </div>
            <input ref={referenceInput} hidden type="file" accept="audio/*" onChange={e => e.target.files?.[0] && uploadReference(e.target.files[0])} />
            <button className="wide-button" onClick={() => referenceInput.current?.click()}>Upload reference voice</button>
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
