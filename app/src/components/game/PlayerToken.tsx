import type { Player } from '../../types/gameTypes'
import type { GamePhase } from '../../types/gameTypes'
import RoleSprite from './RoleSprite'

interface PlayerTokenProps {
  player: Player
  isSpeaker: boolean
  isMarked: boolean
  phase?: GamePhase
  targetPosition: { x: number; y: number }
}

const NIGHT_ROLES = new Set(['werewolf', 'seer', 'witch', 'hunter'])

function PlayerToken({ player, isSpeaker, isMarked, phase, targetPosition }: PlayerTokenProps) {
  const isNightWalking = phase === 'hunt' && isSpeaker && NIGHT_ROLES.has(player.role)
  const tokenClass = `town-token town-token--${player.status}${isSpeaker ? ' town-token--speaker' : ''}${isMarked ? ' town-token--marked' : ''}${isNightWalking ? ' town-token--night-walk' : ''}`

  return (
    <article
      className={tokenClass}
      style={{ left: `${targetPosition.x}%`, top: `${targetPosition.y}%` }}
      aria-label={`${player.id}号 ${player.name}`}
    >
      <div className="town-token__ring" />
      <RoleSprite player={player} active={isSpeaker} phase={phase} />
      <div className="town-token__label">
        <strong>{player.id}</strong>
        <span>{player.name}</span>
      </div>
    </article>
  )
}

export default PlayerToken
