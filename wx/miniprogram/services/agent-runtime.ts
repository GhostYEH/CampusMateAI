export type AgentRisk = 'AUTO_SAFE' | 'CONFIRM_REQUIRED' | 'MANUAL_ONLY' | 'UNKNOWN'

export function safeRisk(value: string): AgentRisk {
  return value === 'AUTO_SAFE' || value === 'CONFIRM_REQUIRED' || value === 'MANUAL_ONLY' ? value : 'UNKNOWN'
}

export function reduceAgentEvents<T extends { id: string; sequence: number }>(events: T[], incoming: T): T[] {
  if (events.some((item) => item.id === incoming.id || item.sequence === incoming.sequence)) return events
  return [...events, incoming].sort((a, b) => a.sequence - b.sequence)
}
