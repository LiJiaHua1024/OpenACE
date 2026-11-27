export type TrackType = 'vocal' | 'accompaniment' | 'audio'

export interface Phoneme {
  symbol: string
  start_ms: number
  duration_ms: number
  is_vowel: boolean
  locked: boolean
}

export interface Note {
  id: string
  start_ticks: number
  duration_ticks: number
  pitch: number
  lyric: string
  velocity: number
  phonemes: Phoneme[]
  pitch_curve: { offset_ms: number; cents: number }[]
  vibrato?: { start_ratio: number; depth_cents: number; frequency_hz: number; phase: number } | null
  techniques: string[]
}

export interface EnvelopePoint {
  ticks: number
  value: number
  curve: string
}

export interface VocalAutomation {
  pitch_cents: EnvelopePoint[]
  dynamic: EnvelopePoint[]
  air: EnvelopePoint[]
  falsetto: EnvelopePoint[]
  tension: EnvelopePoint[]
  energy: EnvelopePoint[]
}


export interface TimedLyric {
  text: string
  start: number
  end: number
}

export interface AudioClip {
  id: string
  path: string
  start_ticks: number
  duration_ticks?: number | null
  offset_ticks?: number
  fade_in_ticks?: number
  fade_out_ticks?: number
  gain_db?: number
  label?: string
  transcribed_lyrics?: TimedLyric[]
}

export type BreathTimbre = 'soft' | 'natural' | 'strong'

export interface Breath {
  id: string
  start_ticks: number
  duration_ticks: number
  intensity: number
  timbre: BreathTimbre
}

export interface Track {
  id: string
  name: string
  type: TrackType
  color: string
  voice_id: string
  reference_voice_path?: string | null
  language: string
  notes: Note[]
  clips: AudioClip[]
  automation: VocalAutomation
  breaths: Breath[]
  mute: boolean
  solo: boolean
  volume: number
  pan: number
  render_path?: string | null
  render_revision: number
}

export interface TimelineState {
  scrollTicks: number
  pxPerBeat: number
}

export interface Project {
  id: string
  schema_version: number
  title: string
  ppq: number
  bpm: number
  tempo_map?: { ticks: number; bpm: number }[]
  time_signature: { numerator: number; denominator: number }
  tracks: Track[]
  created_at: number
  updated_at: number
  metadata: Record<string, any>
}

export interface VoiceProfile {
  id: string
  name: string
  path: string
  created_at: number
  duration_seconds: number
  sample_rate: number
  channels: number
  size_bytes: number
}

export interface RenderJob {
  id: string
  project_id: string
  track_id?: string | null
  mode: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  progress: number
  message: string
  output_path?: string | null
  diagnostic_path?: string | null
  error?: string | null
  engine?: string | null
  fixture?: boolean
  created_at: number
  finished_at?: number | null
}
