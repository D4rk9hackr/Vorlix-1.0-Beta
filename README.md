# 🖐️ Vorlix 1.0 Beta — The AI Hand Control Layer

**Give your AI a real hand to control your computer — lightly, safely, and fast.**

Vorlix is the control-layer engine of **The AI Hand**, a lightweight hybrid architecture that lets an AI agent control your PC using under 200MB of RAM. It escalates through three levels of intervention — always picking the fastest, cheapest method first.

---

## Architecture

```
                    ┌──────────────────┐
                    │   TierRequest    │
                    │  (tool, args,    │
                    │   reasoning,     │
                    │   confidence)    │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   Orchestrator   │
                    │  ─ dispatch() ─  │
                    │  • Loop detect   │
                    │  • Confidence    │
                    │    gate          │
                    │  • Reasoning     │
                    │    required      │
                    │  • Retry logic   │
                    │  • Guardrails    │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌───────────────┐  ┌────────────────┐  ┌──────────────────┐
│  Tier 1       │  │  Tier 1.5      │  │  Tier 2          │
│  Terminal     │  │  System Query  │  │  Web Bridge      │
│  (shell cmds) │  │  (processes,   │  │  (browser DOM    │
│               │  │   windows)     │  │   via extension) │
└───────────────┘  └────────────────┘  └──────────────────┘
                                             │
                                        ┌────▼────┐
                                        │  Tier 3 │
                                        │Computer │
                                        │ Vision  │
                                        │(fallback)│
                                        └─────────┘
                             │
                    ┌────────▼─────────┐
                    │  HumanHelpRequired│
                    │  (escalation)     │
                    └──────────────────┘
```

## Tiers

| Tier | Tool | Description |
|------|------|-------------|
| **1 — Terminal** | `terminal.run_command` | Execute shell commands with destructive-command blacklist |
| **1.5 — System Query** | `process.list` | List running processes (requires `psutil`) |
| | `process.is_running` | Check if a process is running |
| | `window.list` | List open windows (requires `wmctrl` on Linux) |
| | `window.focus` | Focus a window by title |
| | `window.resize` | Resize a window |
| **2 — Web Bridge** | `browser_controls.interact` | Click/type/hover/extract via ARIA roles (Chrome extension) |
| **3 — Computer Vision** | `computer_vision.click_target` | Template-matching click on screen (requires OpenCV) |
| | `computer_vision.track_target` | Continuous tracking with Bezier cursor paths |
| **Time & Reminders** | `time.now` | Current local time |
| | `reminder.create` | Schedule a one-off/repeating reminder |
| | `reminder.list` | List scheduled reminders |
| | `reminder.cancel` | Cancel a reminder |

## Safety features

- **Human override** — freeze all automation instantly via `HumanOverride.freeze()`
- **Loop detection** — identical repeated requests trip detection and escalate
- **Confidence gate** — low-confidence requests require human confirmation
- **Reasoning required** — every action must explain why
- **Guardrails** — destructive commands (`rm -rf /`, `format`, `drop database`, etc.) are hard-blocked
- **Consent-based** — never stealthy, never evades OS permissions

## Quick start

```bash
# Install dependencies
pip install psutil           # System Query tier
pip install opencv-python pyautogui mss numpy  # Computer Vision tier

# Run the CLI
python vorlix_cli/main.py run terminal.run_command --arg command="echo hello" --reason "Testing"
```

### View available skills
```bash
python vorlix_cli/main.py skills
```

### Manage todos
```bash
python vorlix_cli/main.py todo list
python vorlix_cli/main.py todo add "Implement feature X"
```

### Human override
```bash
python vorlix_cli/main.py override status
python vorlix_cli/main.py override stop
python vorlix_cli/main.py override resume
```

## Tests

```bash
python -m pytest tests/ -v
# or
python tests/smoke_test.py
```

## Project structure

```
vorlix/
├── core/                    # Control layer core
│   ├── tier_base.py         # Base classes, enums, dataclasses
│   ├── orchestrator.py      # Request dispatch & routing
│   ├── ledger.py            # Memory & todo tracking
│   ├── human_override.py    # Freeze/resume singleton
│   └── art.py               # ASCII art banners
├── tiers/                   # Tier implementations
│   ├── terminal_tier.py     # Phase 1
│   ├── system_query_tier.py # Phase 1.5
│   ├── computer_vision_tier.py # Phase 3
│   ├── time_reminders_tier.py  # Time awareness
│   └── example_stub_tier.py # Test stub
├── extension/               # Phase 2 — Chrome extension (TypeScript)
│   ├── manifest.json
│   ├── tsconfig.json
│   ├── src/background.ts
│   ├── src/content.ts
│   └── host/native_messaging_host.py
├── skills/                  # Skills registry + SKILL.md files
│   ├── registry.py
│   ├── terminal/SKILL.md
│   ├── system_query/SKILL.md
│   ├── browser_bridge/SKILL.md
│   ├── computer_vision/SKILL.md
│   └── time_reminders/SKILL.md
├── mcp/                     # Lightweight MCP server
│   └── lightweight_server.py
├── vorlix_cli/              # Command-line interface
│   ├── main.py
│   └── formatting.py
├── tests/                   # Test suite (29 tests, all passing)
│   ├── smoke_test.py
│   ├── test_terminal_tier.py
│   ├── test_system_query_tier.py
│   ├── test_computer_vision_tier.py
│   ├── test_time_reminders.py
│   ├── test_skills_registry.py
│   └── test_cli.py
├── pyproject.toml
└── README.md
```

## License

Vorlix Source-Available Commercial License v1.0 — see [LICENSE](./LICENSE) for full terms.

Personal, educational, and non-commercial use is free. Any commercial use (selling, sublicensing, or offering this software as part of a paid product or service) requires a separate license from the copyright holder. Contact: mohamedstngrly@gmail.com

---

**Author:** D4rk9hackr
**Part of:** The AI Hand project
