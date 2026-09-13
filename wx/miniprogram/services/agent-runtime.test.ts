import { reduceAgentEvents, safeRisk } from './agent-runtime'

export function verifyAgentRuntimeContracts(): void {
  if (safeRisk('other') !== 'UNKNOWN') throw new Error('unknown risk must be conservative')
  const one = { id: '1', sequence: 1 }; const two = { id: '2', sequence: 2 }
  const ordered = reduceAgentEvents([two], one)
  if (ordered[0] !== one || ordered[1] !== two) throw new Error('events must be ordered')
  if (reduceAgentEvents(ordered, two).length !== 2) throw new Error('events must be idempotent')
}
