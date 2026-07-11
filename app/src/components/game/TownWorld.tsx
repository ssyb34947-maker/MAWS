import { useEffect, useRef, useState } from 'react'
import type { GameSnapshot } from '../../types/gameTypes'
import HousePlot from './HousePlot'
import PlayerToken from './PlayerToken'

interface TownWorldProps {
  snapshot: GameSnapshot
}

const phaseLabels: Record<GameSnapshot['phase'], string> = {
  daybreak: '天亮',
  discussion: '发言',
  voting: '投票',
  nightfall: '入夜',
  hunt: '夜刀',
  settlement: '结算',
}

// Gathering positions around the town square (day phases)
const GATHERING_POSITIONS: Record<number, { x: number; y: number }> = {
  1: { x: 28, y: 72 },
  2: { x: 42, y: 78 },
  3: { x: 56, y: 78 },
  4: { x: 70, y: 72 },
  5: { x: 22, y: 50 },
  6: { x: 76, y: 50 },
  7: { x: 28, y: 30 },
  8: { x: 68, y: 30 },
}

// Home positions (bottom-center of each house, near door)
const HOME_POSITIONS: Record<number, { x: number; y: number }> = {
  1: { x: 19, y: 42 },
  2: { x: 48, y: 35 },
  3: { x: 79, y: 44 },
  4: { x: 21, y: 84 },
  5: { x: 52, y: 85 },
  6: { x: 81, y: 84 },
  7: { x: 13, y: 64 },
  8: { x: 85, y: 62 },
}

const NIGHT_ROLES = new Set(['werewolf', 'seer', 'witch', 'hunter'])

const VOTE_ARROW_COLORS: Record<string, string> = {
  werewolf: '#d96b72',
  seer: '#6b78c9',
  witch: '#62aaa8',
  hunter: '#d7a34f',
}

function getTargetPosition(
  playerId: number,
  role: string,
  phase: string,
  isSpeaker: boolean,
): { x: number; y: number } {
  const isNightPhase = phase === 'nightfall' || phase === 'hunt'

  if (!isNightPhase) {
    // Day: gather at the square
    return GATHERING_POSITIONS[playerId] ?? { x: 50, y: 50 }
  }

  const home = HOME_POSITIONS[playerId] ?? { x: 50, y: 50 }

  // During hunt, the active role steps forward from their house
  if (phase === 'hunt' && isSpeaker && NIGHT_ROLES.has(role)) {
    return { x: home.x, y: home.y - 12 }
  }

  // Night: stay at home
  return home
}

function getVoteArrowPos(playerId: number, phase: string): { x: number; y: number } {
  const isNightPhase = phase === 'nightfall' || phase === 'hunt'
  if (!isNightPhase) {
    return GATHERING_POSITIONS[playerId] ?? { x: 50, y: 50 }
  }
  return HOME_POSITIONS[playerId] ?? { x: 50, y: 50 }
}

function getArrowColor(role: string, phase: string): string {
  if (phase !== 'hunt') {
    return '#5ba8d6' // Day: blue
  }
  return VOTE_ARROW_COLORS[role] ?? '#5ba8d6'
}

// ---------------------------------------------------------------------------
// VoteArrow sub-component
// ---------------------------------------------------------------------------

interface VoteArrowData {
  id: string
  voterId: number
  targetId: number
  color: string
}

function VoteArrow({ voterId, targetId, color, phase }: VoteArrowData & { phase: string }) {
  const from = getVoteArrowPos(voterId, phase)
  const to = getVoteArrowPos(targetId, phase)

  const dx = to.x - from.x
  const dy = to.y - from.y
  const length = Math.sqrt(dx * dx + dy * dy)
  const angle = Math.atan2(dy, dx) * (180 / Math.PI)

  return (
    <div
      className="vote-arrow"
      style={{
        left: `${from.x}%`,
        top: `${from.y}%`,
        width: `${length}%`,
        transform: `rotate(${angle}deg)`,
        '--arrow-color': color,
      } as React.CSSProperties}
    >
      <div className="vote-arrow__line" style={{ background: color }} />
      <div className="vote-arrow__head" style={{ borderLeftColor: color }} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// TownWorld
// ---------------------------------------------------------------------------

const orchardTiles = Array.from({ length: 18 }, (_, index) => index)

function TownWorld({ snapshot }: TownWorldProps) {
  const isNight = snapshot.phase === 'nightfall' || snapshot.phase === 'hunt'

  // Vote arrow animation state
  const [activeArrows, setActiveArrows] = useState<VoteArrowData[]>([])
  const prevVotesLen = useRef(0)
  const arrowIdRef = useRef(0)

  useEffect(() => {
    if (snapshot.votes.length > prevVotesLen.current) {
      const newVotes = snapshot.votes.slice(prevVotesLen.current)
      const arrows: VoteArrowData[] = []
      for (const vote of newVotes) {
        const voter = snapshot.players.find((p) => p.id === vote.voterId)
        if (voter) {
          const id = `arrow-${++arrowIdRef.current}`
          arrows.push({
            id,
            voterId: vote.voterId,
            targetId: vote.targetId,
            color: getArrowColor(voter.role, snapshot.phase),
          })
        }
      }
      if (arrows.length > 0) {
        setActiveArrows((prev) => [...prev, ...arrows])
        // Auto-remove after animation completes
        const ids = arrows.map((a) => a.id)
        setTimeout(() => {
          setActiveArrows((prev) => prev.filter((a) => !ids.includes(a.id)))
        }, 2600)
      }
    }
    prevVotesLen.current = snapshot.votes.length
  }, [snapshot.votes, snapshot.phase, snapshot.players])

  return (
    <section className={`town-world${isNight ? ' town-world--night' : ''}`} aria-label="狼人杀 2D 小镇主场景">
      <div className="town-world__sky">
        <div className="town-world__sun" />
        <div className="town-world__moon" />
        <div className="town-world__cloud town-world__cloud--one" />
        <div className="town-world__cloud town-world__cloud--two" />
      </div>

      <div className="town-world__map">
        <div className="village-plan" aria-hidden="true">
          <div className="village-plan__road village-plan__road--main" />
          <div className="village-plan__road village-plan__road--cross" />
          <div className="village-plan__road village-plan__road--north" />
          <div className="village-plan__road village-plan__road--south" />
          <div className="village-plan__square">
            <span />
          </div>
          <div className="village-plan__pond" />
          <div className="village-plan__orchard">
            {orchardTiles.map((tile) => (
              <span key={tile} />
            ))}
          </div>
        </div>

        {snapshot.players.map((player) => (
          <HousePlot
            key={`house-${player.id}`}
            player={player}
            active={player.id === snapshot.currentSpeakerId}
            marked={player.id === snapshot.markedTargetId}
          />
        ))}

        <div className="town-world__notice">
          <span>Day {snapshot.day}</span>
          <strong>{phaseLabels[snapshot.phase]}</strong>
        </div>
        <div className="town-world__vote-beam" />
        <div className="town-world__hunt-slash" />

        {snapshot.players.map((player) => (
          <PlayerToken
            key={player.id}
            player={player}
            isSpeaker={player.id === snapshot.currentSpeakerId}
            isMarked={player.id === snapshot.markedTargetId}
            phase={snapshot.phase}
            targetPosition={getTargetPosition(
              player.id,
              player.role,
              snapshot.phase,
              player.id === snapshot.currentSpeakerId,
            )}
          />
        ))}

        {/* Vote arrows */}
        {activeArrows.map((arrow) => (
          <VoteArrow key={arrow.id} {...arrow} phase={snapshot.phase} />
        ))}
      </div>
    </section>
  )
}

export default TownWorld
