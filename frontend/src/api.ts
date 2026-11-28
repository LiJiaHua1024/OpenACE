import type { AudioClip, MediaFile, Note, Project, RenderJob, Track, VoiceProfile } from './types'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`${response.status}: ${text}`)
  }
  return response.json() as Promise<T>
}

function json(init?: object) {
  return { headers: { 'Content-Type': 'application/json' }, ...(init || {}) }
}

export const api = {
  health: () => request<any>('/api/health'),
  listProjects: () => request<any[]>('/api/projects'),
  createProject: (title: string) => request<Project>('/api/projects', json({ method: 'POST', body: JSON.stringify({ title }) })),
  getProject: (id: string) => request<Project>(`/api/projects/${id}`),
  saveProject: (project: Project) => request<Project>(`/api/projects/${project.id}`, json({ method: 'PUT', body: JSON.stringify(project) })),
  duplicateProject: (projectId: string) => request<Project>(`/api/projects/${projectId}/duplicate`, json({ method: 'POST' })),
  deleteProject: (projectId: string) => request<any>(`/api/projects/${projectId}`, { method: 'DELETE' }),
  updateProjectOrganization: (projectId: string, patch: { pinned?: boolean; tags?: string[]; folders?: string[] }) => request<Project>(`/api/projects/${projectId}/organization`, json({ method: 'PATCH', body: JSON.stringify(patch) })),
  addTrack: (projectId: string, payload: object) => request<Track>(`/api/projects/${projectId}/tracks`, json({ method: 'POST', body: JSON.stringify(payload) })),
  addNote: (projectId: string, trackId: string, note: Partial<Note>) => request<Note>(`/api/projects/${projectId}/tracks/${trackId}/notes`, json({ method: 'POST', body: JSON.stringify(note) })),
  updateNote: (projectId: string, trackId: string, noteId: string, patch: Partial<Note>) => request<Note>(`/api/projects/${projectId}/tracks/${trackId}/notes/${noteId}`, json({ method: 'PATCH', body: JSON.stringify(patch) })),
  deleteNote: (projectId: string, trackId: string, noteId: string) => request<any>(`/api/projects/${projectId}/tracks/${trackId}/notes/${noteId}`, { method: 'DELETE' }),
  splitNote: (projectId: string, trackId: string, noteId: string, splitTicks: number) => request<{ first: Note; second: Note }>(`/api/projects/${projectId}/tracks/${trackId}/notes/${noteId}/split`, json({ method: 'POST', body: JSON.stringify({ split_ticks: splitTicks }) })),
  mergeNotes: (projectId: string, trackId: string, noteIds: string[]) => request<Note>(`/api/projects/${projectId}/tracks/${trackId}/notes/merge`, json({ method: 'POST', body: JSON.stringify({ note_ids: noteIds }) })),
  rippleDeleteRange: (projectId: string, startTicks: number, endTicks: number) => request<any>(`/api/projects/${projectId}/editing/ripple-delete-range`, json({ method: 'POST', body: JSON.stringify({ start_ticks: Math.round(startTicks), end_ticks: Math.round(endTicks) }) })),
  renderVocal: (projectId: string, trackId: string) => request<RenderJob>(`/api/projects/${projectId}/render/vocal`, json({ method: 'POST', body: JSON.stringify({ track_id: trackId }) })),
  renderedF0: (projectId: string, trackId: string) => request<{ frame_ms: number; times: number[]; f0_hz: (number | null)[]; source?: string }>(`/api/projects/${projectId}/tracks/${trackId}/rendered-f0`),
  vocal2bgm: (projectId: string, sourceAudio: string, caption: string, trackId?: string, clipId?: string) => request<RenderJob>(`/api/projects/${projectId}/render/vocal2bgm`, json({ method: 'POST', body: JSON.stringify({ source_audio: sourceAudio, caption, track_id: trackId || null, clip_id: clipId || null }) })),
  repaint: (projectId: string, sourceAudio: string, startS: number, endS: number, caption: string, clipId?: string) => request<RenderJob>(`/api/projects/${projectId}/render/repaint`, json({ method: 'POST', body: JSON.stringify({ source_audio: sourceAudio, start_s: startS, end_s: endS, caption, clip_id: clipId || null }) })),
  separate: (projectId: string, sourceAudio: string, clipId?: string) => request<RenderJob>(`/api/projects/${projectId}/render/separate`, json({ method: 'POST', body: JSON.stringify({ source_audio: sourceAudio, clip_id: clipId || null }) })),
  svc: (projectId: string, sourceAudio: string, referenceVoice: string, clipId?: string, transpose?: { pitchShift: number; autoShift: boolean }) => request<RenderJob>(`/api/projects/${projectId}/render/svc`, json({ method: 'POST', body: JSON.stringify({ source_audio: sourceAudio, reference_voice: referenceVoice, clip_id: clipId || null, pitch_shift: transpose?.pitchShift || 0, auto_shift: transpose?.autoShift || false }) })),
  listVoices: () => request<VoiceProfile[]>('/api/voices'),
  renameVoice: (voiceId: string, name: string) => request<VoiceProfile>(`/api/voices/${voiceId}`, json({ method: 'PATCH', body: JSON.stringify({ name }) })),
  trimVoice: (voiceId: string, startSeconds: number, endSeconds: number) => request<VoiceProfile>(`/api/voices/${voiceId}/trim`, json({ method: 'POST', body: JSON.stringify({ start_seconds: startSeconds, end_seconds: endSeconds }) })),
  updateMediaOrganization: (mediaName: string, patch: { tags?: string[]; folders?: string[] }) => request<MediaFile>(`/api/media/${encodeURIComponent(mediaName)}/organization`, json({ method: 'PATCH', body: JSON.stringify(patch) })),
  deleteVoice: (voiceId: string, unassign = false) => request<any>(`/api/voices/${voiceId}${unassign ? '?unassign=true' : ''}`, { method: 'DELETE' }),
  timePhonemes: (symbols: string[], durationMs: number) => request<any[]>('/api/phonemes/time', json({ method: 'POST', body: JSON.stringify({ symbols, duration_ms: durationMs }) })),
  jobs: () => request<RenderJob[]>('/api/jobs'),
  cancelJob: (jobId: string) => request<RenderJob>(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST' }),
  listMedia: () => request<MediaFile[]>('/api/media'),
  deleteMedia: (mediaName: string) => request<any>(`/api/media/${encodeURIComponent(mediaName)}`, { method: 'DELETE' }),
  placeMediaClip: (projectId: string, mediaName: string, startTicks: number, trackId?: string) => request<{ project: Project; track: Track; clip: AudioClip }>(`/api/projects/${projectId}/media/clip`, json({ method: 'POST', body: JSON.stringify({ media_name: mediaName, start_ticks: Math.max(0, Math.round(startTicks)), track_id: trackId || null }) })),
  exportUrl: (projectId: string, fmt: string, range?: { start: number; end: number } | null) => `/api/projects/${projectId}/export/${fmt}${range ? `?start_ticks=${Math.round(range.start)}&end_ticks=${Math.round(range.end)}` : ''}`,
}

export async function uploadFile(file: File): Promise<{ path: string; name: string }> {
  const body = new FormData()
  body.append('file', file)
  const response = await fetch('/api/upload', { method: 'POST', body })
  if (!response.ok) throw new Error(await response.text())
  return response.json()
}

export async function uploadVoice(file: File): Promise<VoiceProfile> {
  const body = new FormData()
  body.append('file', file)
  const response = await fetch('/api/voices', { method: 'POST', body })
  if (!response.ok) throw new Error(await response.text())
  return response.json()
}

export async function importAudio(file: File): Promise<Project> {
  const body = new FormData()
  body.append('file', file)
  const response = await fetch('/api/import/audio', { method: 'POST', body })
  if (!response.ok) throw new Error(await response.text())
  return response.json()
}

export async function importMidi(file: File): Promise<Project> {
  const body = new FormData()
  body.append('file', file)
  const response = await fetch('/api/import/midi', { method: 'POST', body })
  if (!response.ok) throw new Error(await response.text())
  return response.json()
}

export async function importUstx(file: File): Promise<Project> {
  const body = new FormData()
  body.append('file', file)
  const response = await fetch('/api/import/ustx', { method: 'POST', body })
  if (!response.ok) throw new Error(await response.text())
  return response.json()
}

export function voiceAudioUrl(voiceId?: string | null): string | null {
  return voiceId ? `/api/voices/${encodeURIComponent(voiceId)}/audio` : null
}

export function renderFileUrl(path?: string | null): string | null {
  if (!path) return null
  const normalized = path.replace(/\\/g, '/')
  for (const marker of ['/renders/', '/uploads/']) {
    const index = normalized.indexOf(marker)
    if (index >= 0) return marker + normalized.slice(index + marker.length)
  }
  return null
}

export async function importAudioClip(projectId: string, file: File, startTicks: number, trackId?: string): Promise<{ project: Project; track: Track; clip: AudioClip }> {
  const body = new FormData()
  body.append('file', file)
  body.append('start_ticks', String(Math.max(0, Math.round(startTicks))))
  if (trackId) body.append('track_id', trackId)
  const response = await fetch(`/api/projects/${projectId}/clips/import`, { method: 'POST', body })
  if (!response.ok) throw new Error(await response.text())
  return response.json()
}
