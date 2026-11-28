// BS.1770-style K-weighted loudness measurement for OpenACE's local monitor bus.
// The shelf coefficients are the published 48 kHz K-weighting constants. The UI
// labels measurements as approximate whenever the host AudioContext uses another rate.
class OpenACELoudnessProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.exact48k = sampleRate === 48000
    this.shelf = { b: [1.53512485958697, -2.69169618940638, 1.19839281085285], a: [-1.69065929318241, 0.73248077421585] }
    this.highpass = { b: [1, -2, 1], a: [-1.99004745483398, 0.99007225036621] }
    this.states = []
    this.momentaryLength = Math.max(1, Math.round(sampleRate * 0.4))
    this.shortLength = Math.max(1, Math.round(sampleRate * 3.0))
    this.momentaryRing = new Float32Array(this.momentaryLength)
    this.shortRing = new Float32Array(this.shortLength)
    this.momentaryIndex = 0
    this.shortIndex = 0
    this.momentaryFilled = 0
    this.shortFilled = 0
    this.momentarySum = 0
    this.shortSum = 0
    this.framesSincePost = 0
    this.postInterval = Math.max(1, Math.round(sampleRate * 0.1))
    this.port.onmessage = event => {
      if ((event.data || {}).type === 'reset') this.resetMeasurementState()
    }
  }

  resetMeasurementState() {
    this.states = []
    this.momentaryRing.fill(0)
    this.shortRing.fill(0)
    this.momentaryIndex = 0
    this.shortIndex = 0
    this.momentaryFilled = 0
    this.shortFilled = 0
    this.momentarySum = 0
    this.shortSum = 0
    this.framesSincePost = 0
  }

  channelState(channel) {
    while (this.states.length <= channel) {
      this.states.push({ x1: 0, x2: 0, y1: 0, y2: 0, hx1: 0, hx2: 0, hy1: 0, hy2: 0 })
    }
    return this.states[channel]
  }

  kWeighted(sample, state) {
    const shelf = this.shelf
    const shelved = shelf.b[0] * sample + shelf.b[1] * state.x1 + shelf.b[2] * state.x2 - shelf.a[0] * state.y1 - shelf.a[1] * state.y2
    state.x2 = state.x1
    state.x1 = sample
    state.y2 = state.y1
    state.y1 = shelved
    const hp = this.highpass
    const filtered = hp.b[0] * shelved + hp.b[1] * state.hx1 + hp.b[2] * state.hx2 - hp.a[0] * state.hy1 - hp.a[1] * state.hy2
    state.hx2 = state.hx1
    state.hx1 = shelved
    state.hy2 = state.hy1
    state.hy1 = filtered
    return filtered
  }

  pushWindowed(value) {
    if (this.momentaryFilled === this.momentaryLength) this.momentarySum -= this.momentaryRing[this.momentaryIndex]
    else this.momentaryFilled += 1
    this.momentaryRing[this.momentaryIndex] = value
    this.momentarySum += value
    this.momentaryIndex = (this.momentaryIndex + 1) % this.momentaryLength

    if (this.shortFilled === this.shortLength) this.shortSum -= this.shortRing[this.shortIndex]
    else this.shortFilled += 1
    this.shortRing[this.shortIndex] = value
    this.shortSum += value
    this.shortIndex = (this.shortIndex + 1) % this.shortLength
  }

  loudnessFor(sum, count) {
    if (!count) return -120
    const meanSquare = Math.max(1e-14, sum / count)
    return Math.max(-120, -0.691 + 10 * Math.log10(meanSquare))
  }

  process(inputs, outputs) {
    const input = inputs[0]
    const output = outputs[0]
    const frames = input && input.length ? input[0].length : 128
    for (let frame = 0; frame < frames; frame++) {
      let weightedSquareSum = 0
      if (input) {
        for (let channel = 0; channel < input.length; channel++) {
          const sample = input[channel][frame] || 0
          const filtered = this.kWeighted(sample, this.channelState(channel))
          weightedSquareSum += filtered * filtered
          if (output && output[channel]) output[channel][frame] = sample
        }
      }
      this.pushWindowed(weightedSquareSum)
    }
    this.framesSincePost += frames
    if (this.framesSincePost >= this.postInterval) {
      this.framesSincePost = 0
      this.port.postMessage({
        momentary: this.loudnessFor(this.momentarySum, this.momentaryFilled),
        shortTerm: this.loudnessFor(this.shortSum, this.shortFilled),
        exact48k: this.exact48k,
        sampleRate,
      })
    }
    return true
  }
}

registerProcessor('openace-loudness', OpenACELoudnessProcessor)
