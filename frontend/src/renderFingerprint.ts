import type { Project, Track } from './types'

function numberText(value: number): string {
  if (value === 0) return '0'
  const text = value.toFixed(9).replace(/0+$/, '').replace(/\.$/, '')
  return text && text !== '-0' ? text : '0'
}

export function canonicalJson(value: any): string {
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'string') return JSON.stringify(value)
  if (typeof value === 'number') return numberText(value)
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`
  return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`
}

export function fnv1a64(text: string): string {
  let value = 0xcbf29ce484222325n
  const prime = 0x100000001b3n
  const mask = 0xffffffffffffffffn
  for (const byte of new TextEncoder().encode(text)) {
    value ^= BigInt(byte)
    value = (value * prime) & mask
  }
  return value.toString(16).padStart(16, '0')
}

export function vocalRenderInputHash(project: Project, track: Track): string {
  const notes = [...track.notes]
    .sort((a, b) => a.start_ticks - b.start_ticks || a.pitch - b.pitch)
    .map(note => {
      const { id: _id, ...payload } = note as any
      return payload
    })
  const breaths = [...((track as any).breaths || [])]
    .sort((a: any, b: any) => a.start_ticks - b.start_ticks || a.duration_ticks - b.duration_ticks || String(a.id).localeCompare(String(b.id)))
    .map((breath: any) => {
      const { id: _id, ...payload } = breath
      return payload
    })
  const tempoMap: { ticks: number; bpm: number; curve?: 'step' | 'linear' }[] = []
  for (const point of [...(project.tempo_map || [])].filter(point => point.ticks > 0).sort((a, b) => a.ticks - b.ticks)) {
    const normalized = { ticks: Math.trunc(point.ticks), bpm: Math.max(1, point.bpm), curve: point.curve || 'step' as const }
    if (tempoMap.length && tempoMap[tempoMap.length - 1].ticks === normalized.ticks) tempoMap[tempoMap.length - 1] = normalized
    else tempoMap.push(normalized)
  }
  tempoMap.unshift({ ticks: 0, bpm: Math.max(1, project.bpm), curve: 'step' })
  const automation = { ...(track.automation as any) }
  delete automation.volume
  delete automation.pan
  for (const key of Object.keys(automation)) {
    automation[key] = (automation[key] || []).map((point: any) => {
      const copy = { ...point }
      if (copy.voiced == null) delete copy.voiced
      return copy
    })
  }
  return fnv1a64(canonicalJson({
    automation,
    breaths,
    language: track.language,
    notes,
    ppq: project.ppq,
    reference_voice_path: track.reference_voice_path ?? null,
    tempo_map: tempoMap,
    voice_id: (track as any).voice_id ?? null,
  }))
}

export function vocalRenderIsStale(project: Project, track: Track): boolean {
  if (track.type !== 'vocal') return false
  if (!track.render_path) return false
  if (!track.render_fingerprint) return true
  return track.render_fingerprint !== vocalRenderInputHash(project, track)
}
