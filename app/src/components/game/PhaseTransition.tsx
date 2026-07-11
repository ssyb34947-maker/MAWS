import { useEffect, useState } from 'react'

interface PhaseTransitionProps {
  phase: string
  day: number
  onFinish: () => void
}

const TRANSITIONS: Record<string, { text: string; subtitle: string }> = {
  daybreak: { text: '天亮了', subtitle: '第 {day} 天' },
  nightfall: { text: '天黑请闭眼', subtitle: '' },
}

function PhaseTransition({ phase, day, onFinish }: PhaseTransitionProps) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true))
    const timer = setTimeout(() => {
      setVisible(false)
      setTimeout(onFinish, 400)
    }, 1800)
    return () => clearTimeout(timer)
  }, [phase, day, onFinish])

  const info = TRANSITIONS[phase]
  if (!info) return null

  return (
    <div className={`phase-overlay${visible ? ' phase-overlay--show' : ''}`}>
      <div className="phase-overlay__bg" />
      <div className="phase-overlay__content">
        <span className={`phase-overlay__text phase-overlay__text--${phase}`}>
          {info.text}
        </span>
        {info.subtitle && (
          <span className="phase-overlay__sub">
            {info.subtitle.replace('{day}', String(day))}
          </span>
        )}
      </div>
    </div>
  )
}

export default PhaseTransition
