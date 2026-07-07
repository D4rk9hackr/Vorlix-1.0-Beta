"""ASCII art banners for Vorlix CLI."""

VORLIX_BANNER = r"""
╔══════════════════════════════════════════════════════╗
║                                                      ║
║     __     __  _       _     _  __                   ║
║     \ \   / / (_)     | |   (_)/ _|                  ║
║      \ \_/ /   _    __| |    _| |_   ___             ║
║       \   /   | |  / _` |   | |  _| / __|            ║
║        | |    | | | (_| |   | | |   \__ \            ║
║        |_|    |_|  \__,_|   |_|_|   |___/            ║
║                                                      ║
║     The AI Hand — Control Layer Engine v1.0 Beta     ║
║     ⚡ Give your AI a real hand                      ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
"""

TIER_ART = {
    "terminal": """
  ╔══════════════════════╗
  ║  TIER 1: TERMINAL    ║
  ║  ⌨️ Shell Commands   ║
  ╚══════════════════════╝
""",
    "system_query": """
  ╔══════════════════════╗
  ║  TIER 1.5: SYSTEM    ║
  ║  🔍 Process & Windows║
  ╚══════════════════════╝
""",
    "browser_bridge": """
  ╔══════════════════════╗
  ║  TIER 2: WEB BRIDGE  ║
  ║  🌐 DOM Interaction  ║
  ╚══════════════════════╝
""",
    "computer_vision": """
  ╔══════════════════════╗
  ║  TIER 3: COMPUTER    ║
  ║  VISION (Last Resort)║
  ║  👁️ Screen + Mouse   ║
  ╚══════════════════════╝
""",
    "time_reminders": """
  ╔══════════════════════╗
  ║  TIER: TIME &        ║
  ║  REMINDERS           ║
  ║  ⏰ Scheduling       ║
  ╚══════════════════════╝
""",
}

FREEZE_ART = r"""
  ⛔ ⛔ ⛔ ⛔ ⛔ ⛔ ⛔ ⛔ ⛔ ⛔
  ⛔   AUTOMATION FROZEN  ⛔
  ⛔   Human Override     ⛔
  ⛔       ACTIVE         ⛔
  ⛔ ⛔ ⛔ ⛔ ⛔ ⛔ ⛔ ⛔ ⛔ ⛔
"""

RESUME_ART = r"""
  ✅ ✅ ✅ ✅ ✅ ✅ ✅ ✅ ✅ ✅
  ✅   AUTOMATION RESUMED  ✅
  ✅ ✅ ✅ ✅ ✅ ✅ ✅ ✅ ✅ ✅
"""


def print_banner():
    print(VORLIX_BANNER)


def print_tier(name: str):
    art = TIER_ART.get(name)
    if art:
        print(art)


def print_freeze():
    print(FREEZE_ART)


def print_resume():
    print(RESUME_ART)
