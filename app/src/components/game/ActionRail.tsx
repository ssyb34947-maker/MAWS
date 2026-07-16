import type { GameEvent, GamePhase } from '../../types/gameTypes'

interface ActionRailProps {
  events: GameEvent[]
  phase: GamePhase
}

const activePhaseByStep: Record<GameEvent['phase'], GamePhase[]> = {
  daybreak: ['daybreak'],
  discussion: ['discussion'],
  voting: ['voting'],
  nightfall: ['nightfall', 'hunt'],
  hunt: ['nightfall', 'hunt'],
  settlement: ['settlement'],
}

function ActionRail({ events, phase }: ActionRailProps) {
  return (
    <section className="action-rail" aria-label="流程控制区">
      {events.map((event, index) => {
        const activePhases = activePhaseByStep[event.phase] || [event.phase]
        const active = activePhases.includes(phase)
        return (
          <article
            className={`action-step${active ? ' action-step--active' : ''}`}
            key={event.id}
            aria-current={active ? 'step' : undefined}
          >
            <span>{String(index + 1).padStart(2, '0')}</span>
            <div>
              <strong>{event.label}</strong>
              <p>{event.detail}</p>
            </div>
          </article>
        )
      })}
    </section>
  )
}

export default ActionRail
