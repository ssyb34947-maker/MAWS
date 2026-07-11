import { useEffect, useRef, useState } from 'react'

interface GameStartAnimationProps {
  playerCount: number
  onFinish: () => void
}

function GameStartAnimation({ playerCount, onFinish }: GameStartAnimationProps) {
  const [phase, setPhase] = useState<'title' | 'countdown' | 'fadeout'>('title')
  const onFinishRef = useRef(onFinish)
  onFinishRef.current = onFinish

  useEffect(() => {
    const t1 = setTimeout(() => setPhase('countdown'), 1600)
    const t2 = setTimeout(() => setPhase('fadeout'), 3200)
    const t3 = setTimeout(() => onFinishRef.current(), 4000)
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3) }
  }, [])

  return (
    <div className={`start-overlay start-overlay--${phase}`}>
      <div className="start-overlay__bg" />
      <div className="start-overlay__content">
        {phase === 'title' && (
          <div className="start-title">
            <span className="start-title__line start-title__line--top">天黑</span>
            <span className="start-title__line start-title__line--mid">请闭眼</span>
            <span className="start-title__line start-title__line--bot">{playerCount} 名玩家已就位</span>
          </div>
        )}
        {phase === 'countdown' && (
          <div className="start-countdown">
            <span className="start-countdown__label">游戏即将开始</span>
            <span className="start-countdown__roles">
              狼人 · 预言家 · 女巫 · 猎人 · 村民
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

export default GameStartAnimation
