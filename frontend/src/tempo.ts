export interface TempoPoint {
  ticks: number
  bpm: number
}

interface TempoProject {
  ppq: number
  bpm: number
  tempo_map?: TempoPoint[]
  time_signature?: { numerator: number; denominator: number }
}

export function normalizedTempoMap(project: TempoProject): TempoPoint[] {
  const deduped = new Map<number, number>()
  for (const point of project.tempo_map || []) {
    if (point.ticks > 0 && point.bpm > 0) deduped.set(Math.round(point.ticks), point.bpm)
  }
  const later = Array.from(deduped, ([ticks, bpm]) => ({ ticks, bpm })).sort((a, b) => a.ticks - b.ticks)
  return [{ ticks: 0, bpm: Math.max(1, project.bpm || 120) }, ...later]
}

export function bpmAt(project: TempoProject, ticks: number): number {
  let active = normalizedTempoMap(project)[0].bpm
  for (const point of normalizedTempoMap(project)) {
    if (point.ticks <= ticks) active = point.bpm
    else break
  }
  return active
}

export function ticksToSeconds(project: TempoProject, ticks: number): number {
  const points = normalizedTempoMap(project)
  let elapsed = 0
  let cursorTicks = points[0].ticks
  let cursorBpm = points[0].bpm
  if (ticks <= cursorTicks) return (ticks - cursorTicks) / project.ppq * 60 / cursorBpm
  for (const point of points.slice(1)) {
    if (ticks <= point.ticks) return elapsed + (ticks - cursorTicks) / project.ppq * 60 / cursorBpm
    elapsed += (point.ticks - cursorTicks) / project.ppq * 60 / cursorBpm
    cursorTicks = point.ticks
    cursorBpm = point.bpm
  }
  return elapsed + (ticks - cursorTicks) / project.ppq * 60 / cursorBpm
}

export function secondsToTicks(project: TempoProject, seconds: number): number {
  const points = normalizedTempoMap(project)
  const first = points[0]
  if (seconds <= 0) return first.ticks + seconds * first.bpm / 60 * project.ppq
  let elapsed = 0
  let cursorTicks = first.ticks
  let cursorBpm = first.bpm
  for (const point of points.slice(1)) {
    const segmentSeconds = (point.ticks - cursorTicks) / project.ppq * 60 / cursorBpm
    if (seconds <= elapsed + segmentSeconds) return cursorTicks + (seconds - elapsed) * cursorBpm / 60 * project.ppq
    elapsed += segmentSeconds
    cursorTicks = point.ticks
    cursorBpm = point.bpm
  }
  return cursorTicks + (seconds - elapsed) * cursorBpm / 60 * project.ppq
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
