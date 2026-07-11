import type { Player } from '../../types/gameTypes'
import type { GamePhase } from '../../types/gameTypes'

interface RoleSpriteProps {
  player: Player
  active?: boolean
  compact?: boolean
  phase?: GamePhase
}

const roleMarks: Record<Player['role'], string> = {
  villager: '',
  werewolf: 'W',
  seer: 'S',
  witch: '+',
  hunter: 'H',
}

function isNight(phase?: GamePhase) {
  return phase === 'nightfall' || phase === 'hunt'
}

function RoleSprite({ player, active = false, compact = false, phase }: RoleSpriteProps) {
  const night = isNight(phase)
  const nightClass = night ? ` sprite--night-${player.role}` : ''
  const statusClass = `sprite sprite--${player.status}${active ? ' sprite--active' : ''}${compact ? ' sprite--compact' : ''}${nightClass}`

  return (
    <div className={statusClass} aria-label={`${player.id}号 ${player.name} ${player.status}`}>
      <div className="sprite__shadow" />
      <div className="sprite__body" style={{ background: player.avatar.body }}>
        <div className="sprite__hair" style={{ background: player.avatar.hair }} />
        <div className="sprite__face">
          <span />
          <span />
        </div>
        <div className="sprite__vest" style={{ background: player.avatar.vest }} />
        <div className="sprite__badge" style={{ background: player.avatar.accent }}>
          {roleMarks[player.role]}
        </div>
      </div>
      {night && <div className="sprite__aura" />}
    </div>
  )
}

export default RoleSprite
