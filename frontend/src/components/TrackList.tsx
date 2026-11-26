import type { Project, Track } from '../types'

interface Props {
  project: Project
  selectedTrackId?: string
  onSelect(trackId: string): void
  onAddTrack(type: 'vocal' | 'accompaniment'): void
  onPatchTrack(trackId: string, patch: Partial<Track>): void
}

export default function TrackList(props: Props) {
  return (
    <aside className="track-list">
      <div className="panel-title-row">
        <div className="panel-title">Tracks</div>
        <button className="tiny-button" onClick={() => props.onAddTrack('vocal')}>+ Vocal</button>
        <button className="tiny-button" onClick={() => props.onAddTrack('accompaniment')}>+ BGM</button>
      </div>
      <div className="tracks-scroll">
        {props.project.tracks.map(track => (
          <div key={track.id} className={`track-card ${track.id === props.selectedTrackId ? 'selected' : ''}`} onClick={() => props.onSelect(track.id)}>
            <div className="track-color" style={{ background: track.color }} />
            <div className="track-main">
              <input className="track-name" value={track.name} onClick={e => e.stopPropagation()} onChange={e => props.onPatchTrack(track.id, { name: e.target.value })} />
              <div className="track-meta">{track.type} · {track.language} · {track.notes.length} notes</div>
              <div className="track-controls" onClick={e => e.stopPropagation()}>
                <button className={track.mute ? 'toggle active' : 'toggle'} onClick={() => props.onPatchTrack(track.id, { mute: !track.mute })}>M</button>
                <button className={track.solo ? 'toggle active solo' : 'toggle solo'} onClick={() => props.onPatchTrack(track.id, { solo: !track.solo })}>S</button>
                <input title="Volume" type="range" min="0" max="1" step="0.01" value={track.volume} onChange={e => props.onPatchTrack(track.id, { volume: Number(e.target.value) })} />
                <input title="Pan" type="range" min="-1" max="1" step="0.01" value={track.pan} onChange={e => props.onPatchTrack(track.id, { pan: Number(e.target.value) })} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </aside>
  )
}
