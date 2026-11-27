import { useEffect, useState } from 'react'
import type { Project, Track } from '../types'
import LevelMeter from './LevelMeter'
import { vocalRenderIsStale } from '../renderFingerprint'

interface Props {
  project: Project
  selectedTrackId?: string
  onSelect(trackId: string): void
  onAddTrack(type: 'vocal' | 'accompaniment'): void
  onPatchTrack(trackId: string, patch: Partial<Track>): void
  updateProject(mutator: (project: Project) => void, transient?: boolean): void
  getTrackLevel?(trackId: string): number
  getMasterLevel?(): number
}

interface MenuState {
  trackId: string
  x: number
  y: number
}

const TRACK_COLORS = ['#7c5cff', '#2fb996', '#e6a23c', '#e45c7a', '#46a3ff', '#9b7e46']

function uid(prefix: string) {
  return `${prefix}_${crypto.randomUUID().slice(0, 12)}`
}

function duplicateTrackModel(track: Track): Track {
  const copy = JSON.parse(JSON.stringify(track)) as Track
  copy.id = uid('track')
  copy.name = `${track.name} copy`
  copy.notes = copy.notes.map(note => ({ ...note, id: uid('note') }))
  copy.clips = copy.clips.map(clip => ({ ...clip, id: uid('clip') }))
  copy.breaths = copy.breaths.map((breath: any) => ({ ...breath, id: uid('br') }))
  return copy
}

export default function TrackList(props: Props) {
  const [menu, setMenu] = useState<MenuState | null>(null)

  useEffect(() => {
    if (!menu) return
    const close = () => setMenu(null)
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape') close() }
    window.addEventListener('pointerdown', close)
    window.addEventListener('keydown', key)
    return () => {
      window.removeEventListener('pointerdown', close)
      window.removeEventListener('keydown', key)
    }
  }, [menu])

  function openMenu(event: React.MouseEvent, trackId: string) {
    event.preventDefault()
    event.stopPropagation()
    props.onSelect(trackId)
    setMenu({ trackId, x: event.clientX, y: event.clientY })
  }

  function duplicateTrack(trackId: string) {
    let duplicatedId: string | undefined
    props.updateProject(project => {
      const index = project.tracks.findIndex(track => track.id === trackId)
      if (index < 0) return
      const copy = duplicateTrackModel(project.tracks[index])
      duplicatedId = copy.id
      project.tracks.splice(index + 1, 0, copy)
    }, false)
    if (duplicatedId) props.onSelect(duplicatedId)
    setMenu(null)
  }

  function moveTrack(trackId: string, direction: -1 | 1) {
    props.updateProject(project => {
      const index = project.tracks.findIndex(track => track.id === trackId)
      const target = index + direction
      if (index < 0 || target < 0 || target >= project.tracks.length) return
      const [track] = project.tracks.splice(index, 1)
      project.tracks.splice(target, 0, track)
    }, false)
    setMenu(null)
  }

  function deleteTrack(trackId: string) {
    const index = props.project.tracks.findIndex(track => track.id === trackId)
    const fallback = props.project.tracks[index + 1] || props.project.tracks[index - 1]
    props.updateProject(project => {
      const current = project.tracks.findIndex(track => track.id === trackId)
      if (current >= 0) project.tracks.splice(current, 1)
    }, false)
    if (trackId === props.selectedTrackId && fallback) props.onSelect(fallback.id)
    setMenu(null)
  }

  function setTrackColor(trackId: string, color: string) {
    props.updateProject(project => {
      const track = project.tracks.find(item => item.id === trackId)
      if (track) track.color = color
    }, false)
    setMenu(null)
  }

  const menuTrack = menu ? props.project.tracks.find(track => track.id === menu.trackId) : undefined
  const menuIndex = menuTrack ? props.project.tracks.findIndex(track => track.id === menuTrack.id) : -1
  const menuWidth = 176
  const menuHeight = 190
  const menuLeft = menu ? Math.max(6, Math.min(menu.x, window.innerWidth - menuWidth - 6)) : 0
  const menuTop = menu ? Math.max(6, Math.min(menu.y, window.innerHeight - menuHeight - 6)) : 0

  return (
    <aside className="track-list">
      <div className="panel-title-row">
        <div className="panel-title">Tracks</div>
        <button className="tiny-button" onClick={() => props.onAddTrack('vocal')}>+ Vocal</button>
        <button className="tiny-button" onClick={() => props.onAddTrack('accompaniment')}>+ BGM</button>
      </div>
      <div className="tracks-scroll">
        {props.project.tracks.map(track => (
          <div
            key={track.id}
            className={`track-card ${track.id === props.selectedTrackId ? 'selected' : ''}`}
            onClick={() => props.onSelect(track.id)}
            onContextMenu={event => openMenu(event, track.id)}
          >
            <div className="track-color" style={{ background: track.color }} />
            <div className="track-main">
              <div className="track-title-row">
                <input className="track-name" value={track.name} onClick={e => e.stopPropagation()} onChange={e => props.onPatchTrack(track.id, { name: e.target.value })} />
                <button className="track-menu-button" title="Track operations" onClick={event => openMenu(event, track.id)}>⋯</button>
              </div>
              <div className="track-meta">{track.type} · {track.language} · {track.notes.length} notes {vocalRenderIsStale(props.project, track) && <span className="stale-render-badge" title="Notes/expression/tempo/voice changed after this render">stale render</span>}</div>
              {props.getTrackLevel && <LevelMeter compact getLevel={() => props.getTrackLevel!(track.id)} />}
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
      {props.getMasterLevel && (
        <div className="master-meter-row">
          <span>Master</span>
          <LevelMeter getLevel={props.getMasterLevel} />
        </div>
      )}
      {menu && menuTrack && (
        <div
          className="track-context-menu"
          style={{ left: menuLeft, top: menuTop, width: menuWidth }}
          onPointerDown={event => event.stopPropagation()}
          onContextMenu={event => event.preventDefault()}
        >
          <button onClick={() => duplicateTrack(menuTrack.id)}>Duplicate track</button>
          <button disabled={menuIndex <= 0} onClick={() => moveTrack(menuTrack.id, -1)}>Move up</button>
          <button disabled={menuIndex < 0 || menuIndex >= props.project.tracks.length - 1} onClick={() => moveTrack(menuTrack.id, 1)}>Move down</button>
          <div className="track-color-row">
            {TRACK_COLORS.map(color => (
              <button
                key={color}
                className={`track-color-swatch ${menuTrack.color === color ? 'active' : ''}`}
                style={{ background: color }}
                title={`Color ${color}`}
                onClick={() => setTrackColor(menuTrack.id, color)}
              />
            ))}
          </div>
          <button className="danger" onClick={() => deleteTrack(menuTrack.id)}>Delete track</button>
        </div>
      )}
    </aside>
  )
}
