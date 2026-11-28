import type { TimelineState } from './types'

export function zoomTimelineAt(timeline: TimelineState, cursorX: number, gutterWidth: number, factor: number, ppq: number): TimelineState {
  const nextPxPerBeat = Math.max(32, Math.min(360, timeline.pxPerBeat * factor))
  if (Math.abs(nextPxPerBeat - timeline.pxPerBeat) < 1e-9) return timeline
  const anchorX = Math.max(0, cursorX - gutterWidth)
  const anchorTicks = timeline.scrollTicks + (anchorX / timeline.pxPerBeat) * ppq
  const nextScrollTicks = Math.max(0, anchorTicks - (anchorX / nextPxPerBeat) * ppq)
  return { ...timeline, pxPerBeat: nextPxPerBeat, scrollTicks: nextScrollTicks }
}
