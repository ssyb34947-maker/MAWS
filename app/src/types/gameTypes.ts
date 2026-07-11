export type Role = 'werewolf' | 'villager' | 'seer' | 'witch' | 'hunter'

export type Faction = 'town' | 'wolves'

export type GamePhase = 'daybreak' | 'discussion' | 'voting' | 'nightfall' | 'hunt' | 'settlement'

export type PlayerStatus = 'alive' | 'eliminated' | 'protected' | 'targeted'

export interface TownPosition {
  x: number
  y: number
}

export interface PlayerAvatar {
  body: string
  vest: string
  accent: string
  hair: string
}

export interface HousePlot {
  x: number
  y: number
  width: number
  height: number
  roof: string
  wall: string
  yard: string
  crop: string
}

export interface Player {
  id: number
  name: string
  role: Role
  faction: Faction
  status: PlayerStatus
  position: TownPosition
  house: HousePlot
  avatar: PlayerAvatar
  suspicion: number
  voteTarget?: number
  lastAction: string
}

export interface DialogueEntry {
  id: string
  speakerId: number | 'system'
  tone: 'public' | 'private' | 'vote' | 'night' | 'system' | 'werewolf'
  text: string
  timestamp: string
}

export interface VoteRecord {
  voterId: number
  targetId: number
  reason?: string
  resolved?: boolean
}

export interface GameEvent {
  id: string
  phase: GamePhase
  label: string
  detail: string
}

export interface GameSnapshot {
  day: number
  phase: GamePhase
  moon: number
  currentSpeakerId: number
  markedTargetId: number
  players: Player[]
  dialogues: DialogueEntry[]
  votes: VoteRecord[]
  events: GameEvent[]
  winner?: string
}
