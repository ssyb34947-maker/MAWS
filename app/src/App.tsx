import { useState, useRef, useCallback } from 'react'
import GameHero from './components/game/GameHero'
import GameStartAnimation from './components/game/GameStartAnimation'
import PhaseTransition from './components/game/PhaseTransition'
import GameOverScreen from './components/game/GameOverScreen'
import type { GameSnapshot } from './types/gameTypes'
import { gameSnapshot as fallbackSnapshot } from './data/gameData'
import './styles/game.css'

const INITIAL_SNAPSHOT: GameSnapshot = {
  day: 0,
  phase: 'daybreak',
  moon: 8,
  currentSpeakerId: 1,
  markedTargetId: 0,
  players: [],
  dialogues: [],
  votes: [],
  events: [
    { id: 'e1', phase: 'daybreak', label: '天亮公告', detail: '等待游戏开始...' },
  ],
}

function App() {
  const [snapshot, setSnapshot] = useState<GameSnapshot>(INITIAL_SNAPSHOT)
  const [screen, setScreen] = useState<'menu' | 'connecting' | 'playing'>('menu')
  const [showStartAnim, setShowStartAnim] = useState(false)
  const [gameOver, setGameOver] = useState(false)
  const [phaseTrans, setPhaseTrans] = useState<{ phase: string; day: number } | null>(null)
  const [error, setError] = useState('')
  const wsRef = useRef<WebSocket | null>(null)
  const screenRef = useRef(screen)
  const prevPhaseRef = useRef<string>('')
  screenRef.current = screen

  const cleanup = useCallback(() => {
    wsRef.current?.close()
    wsRef.current = null
  }, [])

  const handleStart = useCallback(() => {
    setError('')
    setScreen('connecting')
    setGameOver(false)

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws`
    const ws = new WebSocket(url)

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'start' }))
    }

    ws.onmessage = (event) => {
      let msg: any
      try { msg = JSON.parse(event.data) } catch { return }

      switch (msg.type) {
        case 'game_snapshot':
          {
            const phase = msg.data.phase
            const prevPhase = prevPhaseRef.current
            prevPhaseRef.current = phase
            if (
              prevPhase &&
              phase !== prevPhase &&
              (phase === 'daybreak' || phase === 'nightfall')
            ) {
              setPhaseTrans({ phase, day: msg.data.day })
            }
            setSnapshot(msg.data)
            setScreen('playing')
            if (screenRef.current !== 'playing') {
              setShowStartAnim(true)
            }
          }
          break
        case 'game_over':
          setSnapshot(msg.data)
          setGameOver(true)
          break
        case 'game_reset':
          cleanup()
          setSnapshot(INITIAL_SNAPSHOT)
          setScreen('menu')
          setGameOver(false)
          break
        case 'dialogue':
          setSnapshot((prev) => ({
            ...prev,
            dialogues: [...prev.dialogues, msg.data],
          }))
          break
        case 'vote':
          setSnapshot((prev) => ({
            ...prev,
            votes: [...prev.votes, msg.data],
          }))
          break
      }
    }

    ws.onclose = () => {
      if (screenRef.current === 'connecting') {
        setError('无法连接到游戏服务器')
        setScreen('menu')
      }
    }

    ws.onerror = () => {
      ws.close()
    }

    wsRef.current = ws
  }, [cleanup])

  const handleStop = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: 'stop' }))
    fetch('/api/stop', { method: 'POST' }).catch(() => {})
    cleanup()
    setSnapshot(INITIAL_SNAPSHOT)
    setScreen('menu')
    setGameOver(false)
  }, [cleanup])

  const handleRestart = useCallback(() => {
    cleanup()
    setSnapshot(INITIAL_SNAPSHOT)
    setScreen('menu')
    setGameOver(false)
  }, [cleanup])

  const handleOffline = useCallback(() => {
    setSnapshot(fallbackSnapshot)
    setScreen('playing')
    setShowStartAnim(true)
  }, [])

  if (screen === 'menu') {
    return (
      <main className="game-shell">
        <div className="home-container">
          <div className="home-card">
            <div className="home-header">
              <div className="home-badge">Multi-Agent Werewolf Simulator</div>
              <h1 className="home-title">Agent 小镇狼人杀</h1>
              <p className="home-subtitle">
                基于大语言模型的多智能体博弈推理系统
              </p>
            </div>

            <div className="home-divider" />

            <div className="home-description">
              <p>
                八名 AI 智能体分别扮演狼人、预言家、女巫、猎人与村民，
                通过实时语言对话进行社交推理与阵营博弈。
                每个角色均由独立的大语言模型驱动，具备完整的推理链路与记忆系统。
              </p>
            </div>

            <div className="home-features">
              <div className="home-feature">
                <span className="home-feature__icon">&#9881;</span>
                <div>
                  <strong>LLM 驱动</strong>
                  <span>每个智能体接入独立模型实例</span>
                </div>
              </div>
              <div className="home-feature">
                <span className="home-feature__icon">&#8635;</span>
                <div>
                  <strong>实时推演</strong>
                  <span>完整的昼夜循环与行动结算</span>
                </div>
              </div>
              <div className="home-feature">
                <span className="home-feature__icon">&#9741;</span>
                <div>
                  <strong>记忆系统</strong>
                  <span>智能体基于对话历史自主决策</span>
                </div>
              </div>
            </div>

            {error && <p className="home-error">{error}</p>}

            <div className="home-actions">
              <button className="home-btn home-btn--primary" onClick={handleStart}>
                开始游戏
              </button>
              <button className="home-btn home-btn--secondary" onClick={handleOffline}>
                离线预览
              </button>
            </div>
          </div>
        </div>
      </main>
    )
  }

  if (screen === 'connecting') {
    return (
      <main className="game-shell">
        <div className="home-container">
          <div className="home-card" style={{ textAlign: 'center' }}>
            <h1 className="home-title" style={{ fontSize: '28px', textAlign: 'center' }}>
              Agent 小镇狼人杀
            </h1>
            <div style={{
              width: '48px',
              height: '48px',
              margin: '32px auto',
              border: '3px solid #f5c263',
              borderTopColor: 'transparent',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
            }} />
            <p style={{ color: 'rgba(255,246,216,0.66)', fontSize: '14px', margin: 0 }}>
              AI 智能体正在载入游戏...
            </p>
            <button
              onClick={() => { cleanup(); setScreen('menu') }}
              className="home-btn home-btn--secondary"
              style={{ marginTop: '24px' }}
            >
              取消
            </button>
          </div>
        </div>
      </main>
    )
  }

  return (
    <>
      {showStartAnim && (
        <GameStartAnimation
          playerCount={snapshot.players.length}
          onFinish={() => setShowStartAnim(false)}
        />
      )}
      {phaseTrans && (
        <PhaseTransition
          phase={phaseTrans.phase}
          day={phaseTrans.day}
          onFinish={() => setPhaseTrans(null)}
        />
      )}
      <GameHero snapshot={snapshot} onStop={handleStop} />
      {gameOver && (
        <GameOverScreen snapshot={snapshot} onRestart={handleRestart} />
      )}
    </>
  )
}

export default App
