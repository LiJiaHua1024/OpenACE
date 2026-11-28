import { useEffect, useRef } from 'react'
import type { LoudnessReading } from '../types'

interface Props {
  getReading(): LoudnessReading
  onReset(): void
}

function format(value: number) {
  return value <= -119.5 ? '−∞' : value.toFixed(1)
}

export default function LoudnessMeter(props: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const momentaryRef = useRef<HTMLSpanElement | null>(null)
  const shortTermRef = useRef<HTMLSpanElement | null>(null)
  const maximumRef = useRef<HTMLSpanElement | null>(null)
  const unitRef = useRef<HTMLSpanElement | null>(null)
  const getReadingRef = useRef(props.getReading)
  getReadingRef.current = props.getReading

  useEffect(() => {
    let raf = 0
    const draw = () => {
      const canvas = canvasRef.current
      const reading = getReadingRef.current()
      if (canvas) {
        const width = 190
        const height = 44
        const dpr = window.devicePixelRatio || 1
        if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
          canvas.width = width * dpr
          canvas.height = height * dpr
        }
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
          ctx.clearRect(0, 0, width, height)
          ctx.fillStyle = '#090d16'
          ctx.fillRect(0, 0, width, height)
          const yFor = (loudness: number) => height - 4 - Math.max(0, Math.min(1, (Math.max(-60, loudness) + 60) / 60)) * (height - 8)
          ctx.strokeStyle = '#263044'
          ctx.lineWidth = 1
          for (const target of [-40, -23, -14]) {
            const y = yFor(target)
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke()
            ctx.fillStyle = '#59637c'
            ctx.font = '8px sans-serif'
            ctx.fillText(String(target), 3, Math.max(8, y - 2))
          }
          const points = reading.history.slice(-120)
          const drawLine = (key: 'momentary' | 'shortTerm', color: string) => {
            if (points.length < 2) return
            ctx.strokeStyle = color
            ctx.lineWidth = key === 'shortTerm' ? 1.8 : 1
            ctx.beginPath()
            points.forEach((point, index) => {
              const x = 4 + (index / Math.max(1, points.length - 1)) * (width - 8)
              const y = yFor(point[key])
              if (index === 0) ctx.moveTo(x, y)
              else ctx.lineTo(x, y)
            })
            ctx.stroke()
          }
          drawLine('momentary', '#6fb7ff99')
          drawLine('shortTerm', '#ffd27d')
          if (momentaryRef.current) momentaryRef.current.textContent = `M ${format(reading.momentary)}`
          if (shortTermRef.current) shortTermRef.current.textContent = `S ${format(reading.shortTerm)}`
          if (maximumRef.current) maximumRef.current.textContent = `max ${format(reading.maxShortTerm)}`
          if (unitRef.current) unitRef.current.textContent = `Loudness ${reading.available ? (reading.exact48k ? 'LUFS' : 'LUFS≈') : 'unavailable'}`
          if (!points.length) {
            ctx.fillStyle = '#667089'
            ctx.font = '9px sans-serif'
            ctx.fillText('No playback loudness history', 38, 25)
          }
        }
      }
      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)
    return () => cancelAnimationFrame(raf)
  }, [])

  const reading = props.getReading()
  const unit = reading.exact48k ? 'LUFS' : 'LUFS≈'
  return (
    <div className="loudness-panel" title={reading.exact48k ? 'K-weighted BS.1770-style momentary/short-term loudness at the 48 kHz host monitor rate' : 'K-weighted loudness approximation: host monitor rate is not exactly 48 kHz'}>
      <div className="loudness-head"><span ref={unitRef}>Loudness {reading.available ? unit : 'unavailable'}</span><button onClick={props.onReset}>Reset</button></div>
      <canvas ref={canvasRef} />
      <div className="loudness-values">
        <span ref={momentaryRef}>M {format(reading.momentary)}</span>
        <span ref={shortTermRef}>S {format(reading.shortTerm)}</span>
        <span ref={maximumRef}>max {format(reading.maxShortTerm)}</span>
      </div>
    </div>
  )
}
