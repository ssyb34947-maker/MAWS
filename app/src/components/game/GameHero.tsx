import type { GameSnapshot } from '../../types/gameTypes'
import ActionRail from './ActionRail'
import DialoguePanel from './DialoguePanel'
import StatusBoard from './StatusBoard'
import TownWorld from './TownWorld'

interface GameHeroProps {
  snapshot: GameSnapshot
  onStop?: () => void
}

function GameHero({ snapshot, onStop }: GameHeroProps) {
  return (
    <main className="game-shell">
      <section className="game-hero" aria-label="AI 狼人杀游戏界面">
        <DialoguePanel entries={snapshot.dialogues} players={snapshot.players} />
        <div className="game-stage">
          <div className="game-titlebar">
            <div>
              <span>AI Werewolf Simulator</span>
              <h1>Agent 小镇狼人杀</h1>
            </div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <div className="round-chip">D{snapshot.day} · {snapshot.players.length}人</div>
              <button className="home-btn home-btn--danger" onClick={onStop} title="终止游戏返回首页">
                退出
              </button>
            </div>
          </div>
          <TownWorld snapshot={snapshot} />
          <ActionRail events={snapshot.events} />
        </div>
        <StatusBoard snapshot={snapshot} />
      </section>
    </main>
  )
}

export default GameHero
