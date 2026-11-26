import type { Note, Project, RenderJob, Track } from './types'

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
  addTrack: (projectId: string, payload: object) => request<Track>(`/api/projects/${projectId}/tracks`, json({ method: 'POST', body: JSON.stringify(payload) })),
  addNote: (projectId: string, trackId: string, note: Partial<Note>) => request<Note>(`/api/projects/${projectId}/tracks/${trackId}/notes`, json({ method: 'POST', body: JSON.stringify(note) })),
  updateNote: (projectId: string, trackId: string, noteId: string, patch: Partial<Note>) => request<Note>(`/api/projects/${projectId}/tracks/${trackId}/notes/${noteId}`, json({ method: 'PATCH', body: JSON.stringify(patch) })),
  deleteNote: (projectId: string, trackId: string, noteId: string) => request<any>(`/api/projects/${projectId}/tracks/${trackId}/notes/${noteId}`, { method: 'DELETE' }),
  renderVocal: (projectId: string, trackId: string) => request<RenderJob>(`/api/projects/${projectId}/render/vocal`, json({ method: 'POST', body: JSON.stringify({ track_id: trackId }) })),
  vocal2bgm: (projectId: string, sourceAudio: string, caption: string) => request<RenderJob>(`/api/projects/${projectId}/render/vocal2bgm`, json({ method: 'POST', body: JSON.stringify({ source_audio: sourceAudio, caption }) })),
  repaint: (projectId: string, sourceAudio: string, startS: number, endS: number, caption: string) => request<RenderJob>(`/api/projects/${projectId}/render/repaint`, json({ method: 'POST', body: JSON.stringify({ source_audio: sourceAudio, start_s: startS, end_s: endS, caption }) })),
  svc: (projectId: string, sourceAudio: string, referenceVoice: string) => request<RenderJob>(`/api/projects/${projectId}/render/svc`, json({ method: 'POST', body: JSON.stringify({ source_audio: sourceAudio, reference_voice: referenceVoice }) })),
  timePhonemes: (symbols: string[], durationMs: number) => request<any[]>('/api/phonemes/time', json({ method: 'POST', body: JSON.stringify({ symbols, duration_ms: durationMs }) })),
  jobs: () => request<RenderJob[]>('/api/jobs'),
  exportUrl: (projectId: string, fmt: string) => `/api/projects/${projectId}/export/${fmt}`,
}

export async function uploadFile(file: File): Promise<{ path: string; name: string }> {
  const body = new FormData()
  body.append('file', file)
  const response = await fetch('/api/upload', { method: 'POST', body })
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

export function renderFileUrl(path?: string | null): string | null {
  if (!path) return null
  const normalized = path.replace(/\\/g, '/')
  const marker = '/renders/'
  const index = normalized.indexOf(marker)
  if (index < 0) return null
  return marker + normalized.slice(index + marker.length)
}
