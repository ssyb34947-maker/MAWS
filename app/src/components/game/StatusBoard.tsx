import { useRef, useEffect } from 'react'
import type { GameSnapshot, Player } from '../../types/gameTypes'
import RoleSprite from './RoleSprite'
import { buildStatusSummary, isPlayerAlive } from './statusSelectors'

interface StatusBoardProps {
  snapshot: GameSnapshot
}

const roleLabels: Record<Player['role'], string> = {
  villager: '村民',
  werewolf: '狼人',
  seer: '预言家',
  witch: '女巫',
  hunter: '猎人',
}

const factionLabels: Record<Player['faction'], string> = {
  town: '好人阵营',
  wolves: '狼人阵营',
}

const phaseCopy: Record<GameSnapshot['phase'], string> = {
  daybreak: '天亮公告',
  discussion: '公开发言',
  voting: '投票撮合',
  nightfall: '天黑闭眼',
  hunt: '狼人夜刀',
  settlement: '回合结算',
}

function StatusBoard({ snapshot }: StatusBoardProps) {
  const summary = buildStatusSummary(snapshot.players)
  const voteStackRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const el = voteStackRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [snapshot.votes.length])

  return (
    <aside className="side-panel status-board" aria-label="游戏状态大屏">
      <div className="panel-heading" style={{ gridRow: 1 }}>
        <span>Control Board</span>
        <strong>状态大屏</strong>
      </div>

      <div className="phase-meter" style={{ gridRow: 2 }}>
        <div>
          <span>当前阶段</span>
          <strong>{phaseCopy[snapshot.phase]}</strong>
        </div>
        <div className="phase-meter__orb" style={{ '--moon': `${snapshot.moon}%` } as React.CSSProperties} />
      </div>

      <div className="score-grid score-grid--dynamic" style={{ gridRow: 3 }}>
        <div>
          <span>总人数</span>
          <strong>{summary.total}</strong>
        </div>
        <div>
          <span>存活</span>
          <strong>{summary.alive}</strong>
        </div>
        <div>
          <span>出局</span>
          <strong>{summary.eliminated}</strong>
        </div>
        <div>
          <span>被保护</span>
          <strong>{summary.protected}</strong>
        </div>
        <div>
          <span>被标记</span>
          <strong>{summary.targeted}</strong>
        </div>
        <div>
          <span>轮次</span>
          <strong>D{snapshot.day}</strong>
        </div>
      </div>

      <section className="role-summary" style={{ gridRow: 4 }} aria-label="动态角色数量">
        {summary.roles.map((item) => (
          <article className={`role-summary__item role-summary__item--${item.role}`} key={item.role}>
            <div>
              <strong>{roleLabels[item.role]}</strong>
              <span>{item.alive}/{item.total} 存活</span>
            </div>
            <meter min="0" max={item.total} value={item.alive} aria-label={`${roleLabels[item.role]}存活数量`} />
          </article>
        ))}
      </section>

      <section className="faction-summary" style={{ gridRow: 5 }} aria-label="动态阵营数量">
        {summary.factions.map((item) => (
          <article className={`faction-summary__item faction-summary__item--${item.faction}`} key={item.faction}>
            <span>{factionLabels[item.faction]}</span>
            <strong>{item.alive}/{item.total}</strong>
          </article>
        ))}
      </section>

      <section className="lamp-board" style={{ gridRow: 6 }} aria-label="角色亮灯区">
        {snapshot.players.map((player) => {
          const alive = isPlayerAlive(player.status)
          return (
            <article className={`lamp-tile lamp-tile--${player.status}`} key={player.id}>
              <RoleSprite player={player} compact />
              <div>
                <strong>{player.id}号</strong>
                <span>{roleLabels[player.role]}</span>
              </div>
              <i aria-label={alive ? '存活' : '出局'} />
            </article>
          )
        })}
      </section>

      <section className="vote-stack" ref={voteStackRef} style={{ gridRow: 7 }} aria-label="投票撮合列表">
        <div className="vote-stack__title">投票撮合</div>
        {snapshot.votes.map((vote) => {
          const voter = snapshot.players.find((player) => player.id === vote.voterId)
          const target = snapshot.players.find((player) => player.id === vote.targetId)
          return (
            <div className="vote-row" key={`${vote.voterId}-${vote.targetId}`}>
              <span>{voter?.id}号</span>
              <b />
              <span>{target?.id}号</span>
            </div>
          )
        })}
      </section>
    </aside>
  )
}

export default StatusBoard
