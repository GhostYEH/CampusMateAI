export type AgentRisk = 'AUTO_SAFE' | 'CONFIRM_REQUIRED' | 'MANUAL_ONLY' | 'UNKNOWN'

export function safeRisk(value: string): AgentRisk {
  return value === 'AUTO_SAFE' || value === 'CONFIRM_REQUIRED' || value === 'MANUAL_ONLY' ? value : 'UNKNOWN'
}

export function reduceAgentEvents<T extends { id: string; sequence: number; run_id?: string }>(events: T[], incoming: T): T[] {
  const key = (item: T): string => `${item.run_id ?? ''}:${item.sequence}`
  if (events.some((item) => item.id === incoming.id || key(item) === key(incoming))) return events
  return [...events, incoming].sort((a, b) => a.sequence - b.sequence)
}
