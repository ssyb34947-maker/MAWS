import type { GameEvent } from '../../types/gameTypes'

interface ActionRailProps {
  events: GameEvent[]
}

function ActionRail({ events }: ActionRailProps) {
  return (
    <section className="action-rail" aria-label="流程控制区">
      {events.map((event, index) => (
        <article className={`action-step${index === 2 ? ' action-step--active' : ''}`} key={event.id}>
          <span>{String(index + 1).padStart(2, '0')}</span>
          <div>
            <strong>{event.label}</strong>
            <p>{event.detail}</p>
          </div>
        </article>
      ))}
    </section>
  )
}

export default ActionRail
