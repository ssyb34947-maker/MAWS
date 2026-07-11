import type { Player } from '../../types/gameTypes'

interface HousePlotProps {
  player: Player
  active?: boolean
  marked?: boolean
}

const roleLabels: Record<Player['role'], string> = {
  villager: '村',
  werewolf: '狼',
  seer: '预',
  witch: '巫',
  hunter: '猎',
}

function HousePlot({ player, active = false, marked = false }: HousePlotProps) {
  const plotClass = `house-plot house-plot--${player.status}${active ? ' house-plot--active' : ''}${marked ? ' house-plot--marked' : ''}`

  return (
    <article
      className={plotClass}
      style={{
        left: `${player.house.x}%`,
        top: `${player.house.y}%`,
        width: `${player.house.width}%`,
        height: `${player.house.height}%`,
        '--roof': player.house.roof,
        '--wall': player.house.wall,
        '--yard': player.house.yard,
        '--crop': player.house.crop,
      } as React.CSSProperties}
      aria-label={`${player.id}号 ${player.name} 的房子`}
    >
      <div className="house-plot__yard">
        <div className="house-plot__fence house-plot__fence--top" />
        <div className="house-plot__fence house-plot__fence--bottom" />
        <div className="house-plot__crop-row house-plot__crop-row--one" />
        <div className="house-plot__crop-row house-plot__crop-row--two" />
        <div className="house-plot__home">
          <div className="house-plot__roof" />
          <div className="house-plot__body">
            <span className="house-plot__window" />
            <span className="house-plot__door" />
          </div>
        </div>
        <div className="house-plot__path" />
        <div className="house-plot__plate">
          <strong>{player.id}</strong>
          <span>{roleLabels[player.role]}</span>
        </div>
      </div>
    </article>
  )
}

export default HousePlot
