import { useState } from 'react'
import type { Project } from '../types'
import { beatUnitTicks, ticksToSeconds } from '../tempo'

interface ProjectSummary { id: string; title: string; bpm?: number; track_count?: number; updated_at?: number }
interface Props {
  project: Project
  projects: ProjectSummary[]
  playing: boolean
  playheadTicks: number
  canUndo: boolean
  canRedo: boolean
  onPlayToggle(): void
  onStop(): void
  onSeek(ticks: number): void
  onTitleChange(title: string): void
  onBpmChange(bpm: number): void
  onTimeSignatureChange(numerator: number, denominator: number): void
  onUndo(): void
  onRedo(): void
  onImportMidi(file: File): void
  onImportUstx(file: File): void
  onImportAudio(file: File): void
  importingAudio?: boolean
  onOpenProject(projectId: string): void
  onNewProject(): void
  onDuplicateProject(projectId?: string): void
  onDeleteProject(projectId?: string): void
}

function formatTime(project: Project, ticks: number) {
  const seconds = ticksToSeconds(project, ticks)
  const m = Math.floor(seconds / 60)
  const s = seconds - m * 60
  return `${String(m).padStart(2, '0')}:${s.toFixed(2).padStart(5, '0')}`
}

export default function TransportBar(props: Props) {
  const [managerOpen, setManagerOpen] = useState(false)
  const [search, setSearch] = useState('')
  const unitTicks = beatUnitTicks(props.project)
  const numerator = props.project.time_signature.numerator
  const bars = Math.floor(props.playheadTicks / (unitTicks * numerator)) + 1
  const beatIndex = Math.floor(props.playheadTicks / unitTicks)
  const beats = beatIndex % numerator + 1
  const subdivisions = Math.floor((props.playheadTicks % unitTicks) / (unitTicks / 4)) + 1
  return (
    <header className="transport-bar">
      <div className="brand"><span className="brand-mark">OA</span><span>OpenACE Studio</span><span className="local-badge">LOCAL</span></div>
      <select className="project-select" value={props.project.id} onChange={e => props.onOpenProject(e.target.value)} title="Open project">
        {props.projects.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}
      </select>
      <button className="new-project" onClick={props.onNewProject} title="New project">＋ New</button>
      <button className={`icon-button project-action ${managerOpen ? 'active' : ''}`} onClick={() => setManagerOpen(open => !open)} title="Project manager">Projects</button>
      {managerOpen && (
        <>
          <div className="project-manager-backdrop" onClick={() => setManagerOpen(false)} />
          <div className="project-manager-popover">
          <input className="project-manager-search" autoFocus placeholder="Search projects…" value={search} onChange={event => setSearch(event.target.value)} />
          <div className="project-manager-list">
            {props.projects
              .filter(item => !search.trim() || item.title.toLowerCase().includes(search.trim().toLowerCase()))
              .map(item => (
                <div className={`project-manager-row ${item.id === props.project.id ? 'current' : ''}`} key={item.id}>
                  <button className="project-open-button" onClick={() => { props.onOpenProject(item.id); setManagerOpen(false) }}>
                    <strong>{item.title}</strong>
                    <span>{item.updated_at ? new Date(item.updated_at * 1000).toLocaleDateString() : 'recent'} · {item.track_count ?? '?'} tracks · {item.bpm ?? props.project.bpm} BPM</span>
                  </button>
                  <button onClick={() => { props.onDuplicateProject(item.id); setManagerOpen(false) }}>Copy</button>
                  <button className="danger" onClick={() => props.onDeleteProject(item.id)}>Delete</button>
                </div>
              ))}
            {!props.projects.length && <div className="empty-state">No projects</div>}
          </div>
          </div>
        </>
      )}
      <input className="title-input" value={props.project.title} onChange={e => props.onTitleChange(e.target.value)} />
      <div className="transport-controls">
        <button className="icon-button" title="Undo Ctrl+Z" disabled={!props.canUndo} onClick={props.onUndo}>↶</button>
        <button className="icon-button" title="Redo Ctrl+Y" disabled={!props.canRedo} onClick={props.onRedo}>↷</button>
        <button className="icon-button" title="Stop" onClick={props.onStop}>■</button>
        <button className={`play-button ${props.playing ? 'playing' : ''}`} title="Space" onClick={props.onPlayToggle}>{props.playing ? '❚❚' : '▶'}</button>
      </div>
      <div className="position-readout">
        <strong>{bars}.{beats}.{subdivisions}</strong>
        <span>{formatTime(props.project, props.playheadTicks)}</span>
      </div>
      <label className="tempo-box">BPM
        <input type="number" min="30" max="300" step="0.1" value={props.project.bpm} onChange={e => props.onBpmChange(Number(e.target.value) || props.project.bpm)} />
      </label>
      <select
        className="time-signature-select"
        title="Time signature"
        value={`${props.project.time_signature.numerator}/${props.project.time_signature.denominator}`}
        onChange={event => {
          const [numerator, denominator] = event.target.value.split('/').map(Number)
          props.onTimeSignatureChange(numerator, denominator)
        }}
      >
        {['2/4', '3/4', '4/4', '5/4', '6/8', '7/8', '9/8', '12/8'].map(value => <option key={value} value={value}>{value}</option>)}
      </select>
      <label className="import-midi">Import MIDI
        <input type="file" accept=".mid,.midi" onChange={e => e.target.files?.[0] && props.onImportMidi(e.target.files[0])} />
      </label>
      <label className="import-midi">Import USTX
        <input type="file" accept=".ustx,.zip" onChange={e => e.target.files?.[0] && props.onImportUstx(e.target.files[0])} />
      </label>
      <label className={`import-midi ${props.importingAudio ? 'importing' : ''}`}>{props.importingAudio ? 'Transcribing audio…' : 'Import audio'}
        <input type="file" accept="audio/*,.wav,.mp3,.flac" disabled={props.importingAudio} onChange={e => e.target.files?.[0] && props.onImportAudio(e.target.files[0])} />
      </label>
    </header>
  )
}
