import { useEffect, useRef } from 'react'

interface Props {
  getLevel(): number
  compact?: boolean
}

export default function LevelMeter(props: Props) {
  const fillRef = useRef<HTMLDivElement | null>(null)
  const getLevelRef = useRef(props.getLevel)
  getLevelRef.current = props.getLevel

  useEffect(() => {
    let raf = 0
    let smoothed = 0
    const tick = () => {
      const raw = Math.max(0, Math.min(1, getLevelRef.current()))
      smoothed = raw > smoothed ? raw : smoothed * 0.84
      const width = Math.pow(smoothed, 0.68)
      const fill = fillRef.current
      if (fill) {
        fill.style.transform = `scaleX(${width})`
        fill.classList.toggle('hot', smoothed > 0.88)
        fill.classList.toggle('warm', smoothed > 0.62 && smoothed <= 0.88)
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])

  return (
    <div className={`level-meter ${props.compact ? 'compact' : ''}`} aria-hidden="true">
      <div ref={fillRef} className="level-meter-fill" />
    </div>
  )
}
