import { AgentEventReducer } from '../../main/ets/service/AgentEventReducer';
import { parseAgentRisk, parseAgentStatus } from '../../main/ets/data/AgentRuntimeModels';

export default function agentRuntimeModelsTest(): void {
  expect(parseAgentStatus('not-a-status')).assertEqual('UNKNOWN');
  expect(parseAgentRisk('not-a-risk')).assertEqual('UNKNOWN');
  const reducer: AgentEventReducer = new AgentEventReducer();
  const event = { id: 'e1', type: 'RUN', run_id: 'r1', sequence: 1, status: 'RUNNING', phase: 'IDLE', summary: '安全摘要', progress: { current: 1, total: 1, percent: 100 } };
  expect(reducer.reduce(event as never).length).assertEqual(1);
  expect(reducer.reduce(event as never).length).assertEqual(1);
}
