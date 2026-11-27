import type { AudioClip, Track } from './types'

export interface CrossfadeInterval {
  startTicks: number
  endTicks: number
  role: 'outgoing' | 'incoming'
  otherClipId: string
}

function orderedClips(track: Track) {
  return [...track.clips].sort((a, b) => a.start_ticks - b.start_ticks || a.id.localeCompare(b.id))
}

export function crossfadeIntervals(track: Track, clip: AudioClip): CrossfadeInterval[] {
  if (!clip.duration_ticks || clip.duration_ticks <= 0) return []
  const ordered = orderedClips(track)
  const positions = new Map(ordered.map((item, index) => [item.id, index]))
  const clipStart = clip.start_ticks
  const clipEnd = clip.start_ticks + clip.duration_ticks
  const intervals: CrossfadeInterval[] = []
  for (const other of ordered) {
    if (other.id === clip.id || !other.duration_ticks || other.duration_ticks <= 0) continue
    const start = Math.max(clipStart, other.start_ticks)
    const end = Math.min(clipEnd, other.start_ticks + other.duration_ticks)
    if (end <= start) continue
    intervals.push({
      startTicks: start,
      endTicks: end,
      role: (positions.get(clip.id) || 0) < (positions.get(other.id) || 0) ? 'outgoing' : 'incoming',
      otherClipId: other.id,
    })
  }
  return intervals
}

export function crossfadeGainAt(track: Track, clip: AudioClip, positionTicks: number): number {
  let gain = 1
  for (const interval of crossfadeIntervals(track, clip)) {
    if (positionTicks < interval.startTicks || positionTicks > interval.endTicks) continue
    const progress = Math.max(0, Math.min(1, (positionTicks - interval.startTicks) / Math.max(1e-9, interval.endTicks - interval.startTicks)))
    gain *= interval.role === 'outgoing' ? Math.cos(progress * Math.PI / 2) : Math.sin(progress * Math.PI / 2)
  }
  return gain
}
