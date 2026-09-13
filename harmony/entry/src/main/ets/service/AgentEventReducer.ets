import { AgentEvent } from '../data/AgentRuntimeModels';

export class AgentEventReducer {
  private events: AgentEvent[] = [];

  reduce(event: AgentEvent): AgentEvent[] {
    if (this.events.some((item: AgentEvent) => item.id === event.id || item.sequence === event.sequence)) return this.events;
    this.events.push(event);
    this.events.sort((left: AgentEvent, right: AgentEvent) => left.sequence - right.sequence);
    return this.events.slice();
  }

  snapshot(): AgentEvent[] { return this.events.slice(); }
}
