import type { Faction, Player, PlayerStatus, Role } from '../../types/gameTypes'

export interface RoleSummaryItem {
  role: Role
  total: number
  alive: number
  eliminated: number
}

export interface FactionSummaryItem {
  faction: Faction
  total: number
  alive: number
}

export interface StatusSummary {
  total: number
  alive: number
  eliminated: number
  protected: number
  targeted: number
  roles: RoleSummaryItem[]
  factions: FactionSummaryItem[]
}

const aliveStatuses: PlayerStatus[] = ['alive', 'protected', 'targeted']

export function isPlayerAlive(status: PlayerStatus): boolean {
  return aliveStatuses.includes(status)
}

export function buildStatusSummary(players: Player[]): StatusSummary {
  const roleOrder: Role[] = []
  const factionOrder: Faction[] = []
  const roles = new Map<Role, RoleSummaryItem>()
  const factions = new Map<Faction, FactionSummaryItem>()

  let alive = 0
  let eliminated = 0
  let protectedCount = 0
  let targeted = 0

  for (const player of players) {
    const playerAlive = isPlayerAlive(player.status)
    if (playerAlive) alive += 1
    if (player.status === 'eliminated') eliminated += 1
    if (player.status === 'protected') protectedCount += 1
    if (player.status === 'targeted') targeted += 1

    if (!roles.has(player.role)) {
      roleOrder.push(player.role)
      roles.set(player.role, { role: player.role, total: 0, alive: 0, eliminated: 0 })
    }
    const roleSummary = roles.get(player.role)
    if (roleSummary) {
      roleSummary.total += 1
      if (playerAlive) roleSummary.alive += 1
      if (player.status === 'eliminated') roleSummary.eliminated += 1
    }

    if (!factions.has(player.faction)) {
      factionOrder.push(player.faction)
      factions.set(player.faction, { faction: player.faction, total: 0, alive: 0 })
    }
    const factionSummary = factions.get(player.faction)
    if (factionSummary) {
      factionSummary.total += 1
      if (playerAlive) factionSummary.alive += 1
    }
  }

  return {
    total: players.length,
    alive,
    eliminated,
    protected: protectedCount,
    targeted,
    roles: roleOrder.map((role) => roles.get(role)).filter((item): item is RoleSummaryItem => Boolean(item)),
    factions: factionOrder.map((faction) => factions.get(faction)).filter((item): item is FactionSummaryItem => Boolean(item)),
  }
}
