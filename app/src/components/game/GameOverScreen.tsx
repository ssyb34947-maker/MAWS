import { useEffect, useState } from 'react'
import type { GameSnapshot, Player } from '../../types/gameTypes'

interface GameOverScreenProps {
  snapshot: GameSnapshot
  onRestart: () => void
}

const roleLabels: Record<Player['role'], string> = {
  villager: '村民',
  werewolf: '狼人',
  seer: '预言家',
  witch: '女巫',
  hunter: '猎人',
}

const factionLabels: Record<string, string> = {
  wolves: '狼人阵营',
  town: '好人阵营',
}

function GameOverScreen({ snapshot, onRestart }: GameOverScreenProps) {
  const [visible, setVisible] = useState(false)
  const [revealRoles, setRevealRoles] = useState(false)

  const winner = snapshot.winner || ''
  const isWolfWin = winner === 'werewolves'
  const isDraw = winner === 'draw'
  const winnerLabel = isDraw ? '平局' : isWolfWin ? '狼人阵营' : '好人阵营'
  const winnerEmoji = isDraw ? '🤝' : isWolfWin ? '🐺' : '👑'

  useEffect(() => {
    const t1 = setTimeout(() => setVisible(true), 100)
    const t2 = setTimeout(() => setRevealRoles(true), 1200)
    return () => { clearTimeout(t1); clearTimeout(t2) }
  }, [])

  return (
    <div className="gameover-overlay">
      <div className={`gameover-card${visible ? ' gameover-card--show' : ''}`}>
        <div className="gameover-badge">{winnerEmoji}</div>
        <h1 className={`gameover-title gameover-title--${isDraw ? 'draw' : isWolfWin ? 'werewolves' : 'villagers'}`}>
          {winnerLabel} 获胜！
        </h1>
        <p className="gameover-subtitle">
          第 {snapshot.day} 天 · {snapshot.players.length} 名玩家
        </p>

        <div className="gameover-divider" />

        <div className={`gameover-roles${revealRoles ? ' gameover-roles--show' : ''}`}>
          <h2>角色揭晓</h2>
          <div className="gameover-roles__grid">
            {snapshot.players.map((player) => {
              const alive = player.status === 'alive'
              return (
                <article
                  className={`gameover-player${alive ? ' gameover-player--alive' : ''}`}
                  key={player.id}
                >
                  <span className="gameover-player__id">{player.id}号</span>
                  <span className={`gameover-player__role gameover-player__role--${player.role}`}>
                    {roleLabels[player.role]}
                  </span>
                  <span className={`gameover-player__faction gameover-player__faction--${player.faction}`}>
                    {factionLabels[player.faction] || (player.faction === 'town' ? '好人阵营' : '狼人阵营')}
                  </span>
                  <span className="gameover-player__status">
                    {alive ? '存活' : '出局'}
                  </span>
                </article>
              )
            })}
          </div>
        </div>

        <button className="home-btn home-btn--primary" onClick={onRestart} style={{ marginTop: '24px' }}>
          返回首页
        </button>
      </div>
    </div>
  )
}

export default GameOverScreen
