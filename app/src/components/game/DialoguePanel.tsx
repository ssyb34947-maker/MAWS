import { useRef, useEffect, useState } from 'react'
import type { DialogueEntry, Player } from '../../types/gameTypes'

interface DialoguePanelProps {
  entries: DialogueEntry[]
  players: Player[]
}

type FilterMode = 'all' | 'public' | 'werewolf' | 'night' | 'system'

const toneLabels: Record<DialogueEntry['tone'], string> = {
  public: '发言',
  private: '私密',
  vote: '投票理由',
  night: '夜间',
  system: '系统',
  werewolf: '狼人',
}

const FILTERS: { key: FilterMode; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'public', label: '公开' },
  { key: 'werewolf', label: '狼人' },
  { key: 'night', label: '夜间' },
  { key: 'system', label: '系统' },
]

const TONE_FILTER_MAP: Record<FilterMode, DialogueEntry['tone'][]> = {
  all: ['public', 'private', 'vote', 'night', 'system', 'werewolf'],
  public: ['public'],
  werewolf: ['werewolf'],
  night: ['night', 'werewolf'],
  system: ['system'],
}

function DialoguePanel({ entries, players }: DialoguePanelProps) {
  const [filter, setFilter] = useState<FilterMode>('all')
  const listRef = useRef<HTMLDivElement>(null)
  const nameById = new Map(players.map((player) => [player.id, `${player.id}号 ${player.name}`]))

  const filtered =
    filter === 'all'
      ? entries
      : entries.filter((e) => TONE_FILTER_MAP[filter].includes(e.tone))

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    const el = listRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [filtered.length])

  return (
    <aside className="side-panel dialogue-panel" aria-label="发言与事件列表">
      <div className="panel-heading">
        <span>Village Feed</span>
        <strong>发言流</strong>
      </div>

      <div className="dialogue-filters">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`dialogue-filter-btn${filter === f.key ? ' dialogue-filter-btn--active' : ''}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="dialogue-list" ref={listRef}>
        {filtered.map((entry) => (
          <article className={`dialogue-card dialogue-card--${entry.tone}`} key={entry.id}>
            <div className="dialogue-card__meta">
              <span>{entry.speakerId === 'system' ? '系统' : nameById.get(entry.speakerId)}</span>
              <time>{entry.timestamp}</time>
            </div>
            <p>{entry.text}</p>
            <b>{toneLabels[entry.tone]}</b>
          </article>
        ))}
      </div>
    </aside>
  )
}

export default DialoguePanel
