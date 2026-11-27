import type { Project } from '../types'
import { beatUnitTicks, ticksToSeconds } from '../tempo'

interface ProjectSummary { id: string; title: string }
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
  onDuplicateProject(): void
  onDeleteProject(): void
}

function formatTime(project: Project, ticks: number) {
  const seconds = ticksToSeconds(project, ticks)
  const m = Math.floor(seconds / 60)
  const s = seconds - m * 60
  return `${String(m).padStart(2, '0')}:${s.toFixed(2).padStart(5, '0')}`
}

export default function TransportBar(props: Props) {
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
      <button className="icon-button project-action" onClick={props.onDuplicateProject} title="Duplicate project">Copy</button>
      <button className="icon-button project-action danger" onClick={props.onDeleteProject} title="Delete project">×</button>
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
