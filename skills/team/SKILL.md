# Team Agent

Multi-agent collaboration — when the AI needs help, it spawns sub-agents.

Each sub-agent is an independent worker with its own tool access, goal, and
execution context. Sub-agents run concurrently and report results back.

## Tools
### `subagent.spawn`
Spawn a new sub-agent with a goal.
- `goal`: what the sub-agent should accomplish (can include tool calls)
- `tools`: comma-separated allowed tool names, or `*` for all

### `subagent.ask`
Delegate additional work to a spawned sub-agent.
- `agent_id`: the sub-agent's id
- `task`: task description or tool call for the sub-agent

### `subagent.list`
List all spawned sub-agents and their status.
- `agent_id`: optional — get details on a specific sub-agent

### `subagent.kill`
Terminate and remove a sub-agent.
- `agent_id`: the sub-agent's id

### `subagent.collect`
Wait for sub-agents to complete and collect results.
- `agent_id`: optional — wait for a specific sub-agent
- `timeout`: seconds to wait (default 30)

## Resource Cost
Minimal. Sub-agents reuse the existing orchestrator and tiers. Each sub-agent
is a lightweight async task.
