import type { GameSnapshot } from '../types/gameTypes'

export type WsMessage =
  | { type: 'connected'; data: { message: string } }
  | { type: 'game_snapshot'; data: GameSnapshot }
  | { type: 'dialogue'; data: GameSnapshot['dialogues'][number] }
  | { type: 'vote'; data: GameSnapshot['votes'][number] }
  | { type: 'game_over'; data: GameSnapshot & { winner: string } }
  | { type: 'log'; data: string }
  | { type: 'pong' }

export type WsHandler = (msg: WsMessage) => void

export function createGameSocket(handlers: {
  onMessage?: WsHandler
  onOpen?: () => void
  onClose?: () => void
  onError?: (err: Event) => void
}): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const url = `${protocol}//${host}/ws`

  const ws = new WebSocket(url)

  ws.onopen = () => {
    handlers.onOpen?.()
  }

  ws.onclose = () => {
    handlers.onClose?.()
  }

  ws.onerror = (err) => {
    handlers.onError?.(err)
  }

  ws.onmessage = (event) => {
    try {
      const msg: WsMessage = JSON.parse(event.data)
      handlers.onMessage?.(msg)
    } catch (e) {
      console.warn('Failed to parse WS message:', e)
    }
  }

  // Keep alive ping every 30 seconds
  const pingInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }))
    }
  }, 30000)

  // Clean up interval on close
  ws.addEventListener('close', () => clearInterval(pingInterval))

  return ws
}
