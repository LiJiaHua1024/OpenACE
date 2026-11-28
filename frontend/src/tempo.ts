export interface TempoPoint {
  ticks: number
  bpm: number
  curve?: 'step' | 'linear'
}

interface TempoProject {
  ppq: number
  bpm: number
  tempo_map?: TempoPoint[]
  time_signature?: { numerator: number; denominator: number }
}

export function normalizedTempoMap(project: TempoProject): TempoPoint[] {
  const deduped = new Map<number, TempoPoint>()
  for (const point of project.tempo_map || []) {
    if (point.ticks > 0 && point.bpm > 0) deduped.set(Math.round(point.ticks), { ...point, ticks: Math.round(point.ticks), curve: point.curve || 'step' })
  }
  const later = Array.from(deduped.values()).sort((a, b) => a.ticks - b.ticks)
  return [{ ticks: 0, bpm: Math.max(1, project.bpm || 120), curve: 'step' }, ...later]
}

export function bpmAt(project: TempoProject, ticks: number): number {
  const points = normalizedTempoMap(project)
  if (ticks <= points[0].ticks) return points[0].bpm
  for (let index = 1; index < points.length; index++) {
    const point = points[index]
    if (ticks <= point.ticks) {
      const previous = points[index - 1]
      if (ticks < point.ticks) {
        if (point.curve === 'linear' && point.ticks > previous.ticks) {
          const ratio = Math.max(0, Math.min(1, (ticks - previous.ticks) / (point.ticks - previous.ticks)))
          return previous.bpm + (point.bpm - previous.bpm) * ratio
        }
        return previous.bpm
      }
      return point.bpm
    }
  }
  return points[points.length - 1].bpm
}

function segmentSeconds(project: TempoProject, startTicks: number, endTicks: number, startBpm: number, endBpm: number, linear: boolean): number {
  const span = endTicks - startTicks
  if (!span) return 0
  if (!linear || Math.abs(endBpm - startBpm) < 1e-9) return span / project.ppq * 60 / startBpm
  return 60 / project.ppq * span / (endBpm - startBpm) * Math.log(endBpm / startBpm)
}

function invertLinearSegment(project: TempoProject, seconds: number, startTicks: number, endTicks: number, startBpm: number, endBpm: number): number {
  const span = endTicks - startTicks
  if (Math.abs(endBpm - startBpm) < 1e-9) return startTicks + seconds * startBpm / 60 * project.ppq
  const bpm = startBpm * Math.exp(seconds * project.ppq / 60 * (endBpm - startBpm) / span)
  return startTicks + span * (bpm - startBpm) / (endBpm - startBpm)
}

export function ticksToSeconds(project: TempoProject, ticks: number): number {
  const points = normalizedTempoMap(project)
  const first = points[0]
  if (ticks <= first.ticks) return (ticks - first.ticks) / project.ppq * 60 / first.bpm
  let elapsed = 0
  let previous = first
  for (const point of points.slice(1)) {
    if (ticks <= point.ticks) {
      if (point.curve === 'linear') {
        const ratio = (ticks - previous.ticks) / Math.max(1e-9, point.ticks - previous.ticks)
        const endBpm = previous.bpm + (point.bpm - previous.bpm) * ratio
        return elapsed + segmentSeconds(project, previous.ticks, ticks, previous.bpm, endBpm, true)
      }
      return elapsed + (ticks - previous.ticks) / project.ppq * 60 / previous.bpm
    }
    elapsed += segmentSeconds(project, previous.ticks, point.ticks, previous.bpm, point.bpm, point.curve === 'linear')
    previous = point
  }
  return elapsed + (ticks - previous.ticks) / project.ppq * 60 / previous.bpm
}

export function secondsToTicks(project: TempoProject, seconds: number): number {
  const points = normalizedTempoMap(project)
  const first = points[0]
  if (seconds <= 0) return first.ticks + seconds * first.bpm / 60 * project.ppq
  let elapsed = 0
  let previous = first
  for (const point of points.slice(1)) {
    const segment = segmentSeconds(project, previous.ticks, point.ticks, previous.bpm, point.bpm, point.curve === 'linear')
    if (seconds <= elapsed + segment) {
      if (point.curve === 'linear') return invertLinearSegment(project, seconds - elapsed, previous.ticks, point.ticks, previous.bpm, point.bpm)
      return previous.ticks + (seconds - elapsed) * previous.bpm / 60 * project.ppq
    }
    elapsed += segment
    previous = point
  }
  return previous.ticks + (seconds - elapsed) * previous.bpm / 60 * project.ppq
}

export function secondsBetweenTicks(project: TempoProject, startTicks: number, endTicks: number): number {
  return ticksToSeconds(project, endTicks) - ticksToSeconds(project, startTicks)
}

export function tickDurationSeconds(project: TempoProject, startTicks: number, durationTicks: number): number {
  return secondsBetweenTicks(project, startTicks, startTicks + durationTicks)
}

export function secondsToTicksFrom(project: TempoProject, startTicks: number, seconds: number): number {
  return secondsToTicks(project, ticksToSeconds(project, startTicks) + seconds) - startTicks
}

export function beatUnitTicks(project: TempoProject): number {
  return project.ppq * 4 / Math.max(1, project.time_signature?.denominator || 4)
}

export function barTicks(project: TempoProject): number {
  return Math.max(1, project.time_signature?.numerator || 4) * beatUnitTicks(project)
}
