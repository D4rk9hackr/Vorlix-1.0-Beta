"""Skills registry — list, activate, deactivate tiers."""
import importlib
import inspect
import os
import sys
from typing import Dict, List, Optional, Tuple

from core.tier_base import AutomationTier

SKILLS_DIR = os.path.dirname(os.path.abspath(__file__))


def _skill_path(name: str) -> str:
    return os.path.join(SKILLS_DIR, name)


def _read_skill_metadata(name: str) -> Optional[dict]:
    md_path = os.path.join(_skill_path(name), "SKILL.md")
    if not os.path.exists(md_path):
        return None
    meta = {"name": name, "description": "", "tools": [], "resource_cost": ""}
    with open(md_path, encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    in_tools = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## Description"):
            continue
        if stripped.startswith("## Tools"):
            in_tools = True
            continue
        if stripped.startswith("## Resource Cost"):
            meta["resource_cost"] = lines[lines.index(line) + 1].strip() if lines.index(line) + 1 < len(lines) else ""
            in_tools = False
            continue
        if in_tools and stripped.startswith("### `"):
            tool_name = stripped.split("`")[1]
            meta["tools"].append(tool_name)
        if stripped.startswith("Provides") or stripped.startswith("Lightweight"):
            meta["description"] = stripped

    return meta


def list_skills() -> List[dict]:
    """Read SKILL.md metadata for each skill directory (cheap, no imports)."""
    skills = []
    for entry in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, entry)
        if os.path.isdir(skill_dir) and not entry.startswith("__"):
            meta = _read_skill_metadata(entry)
            if meta:
                skills.append(meta)
    return skills


def activate_skill(name: str) -> Tuple[bool, str, Optional[AutomationTier]]:
    """Import and instantiate a skill's tool.py. Returns (success, message, tier)."""
    skill_dir = _skill_path(name)
    tool_path = os.path.join(skill_dir, "tool.py")
    if not os.path.exists(tool_path):
        # Fall back: look in tiers/ for a matching tier
        tiers_dir = os.path.join(os.path.dirname(SKILLS_DIR), "tiers")
        tier_map = {
            "terminal": "terminal_tier",
            "system_query": "system_query_tier",
            "browser_bridge": None,
            "computer_vision": "computer_vision_tier",
            "time_reminders": "time_reminders_tier",
            "auto_debug": "file_io_tier",
        }
        module_name = tier_map.get(name)
        if not module_name:
            return False, f"No tool.py found for skill '{name}' and no tier mapping exists.", None

        module_path = f"tiers.{module_name}"
        if module_path not in sys.modules:
            try:
                importlib.import_module(module_path)
            except ImportError as e:
                return False, f"Failed to import {module_path}: {e}", None

        module = sys.modules[module_path]
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, AutomationTier) and obj is not AutomationTier:
                tier = obj()
                tier_name = tier.name
                return True, f"Skill '{name}' activated as {tier_name}.", tier

        return False, f"No AutomationTier subclass found in {module_path}.", None

    # Load from tool.py in skill directory
    spec = importlib.util.spec_from_file_location(f"skills.{name}.tool", tool_path)
    if spec is None or spec.loader is None:
        return False, f"Failed to load tool.py for skill '{name}'.", None

    module = importlib.util.module_from_spec(spec)
    sys.modules[f"skills.{name}.tool"] = module
    spec.loader.exec_module(module)

    for _, obj in inspect.getmembers(module, inspect.isclass):
        if issubclass(obj, AutomationTier) and obj is not AutomationTier:
            tier = obj()
            return True, f"Skill '{name}' activated as {tier.name}.", tier

    return False, f"No AutomationTier subclass found in skills/{name}/tool.py.", None


def deactivate_skill(name: str) -> bool:
    """Remove a skill's module from sys.modules if loaded."""
    module_names = [
        f"skills.{name}.tool",
        f"skills.{name}",
        f"tiers.{name}_tier",
    ]
    for mod_name in module_names:
        if mod_name in sys.modules:
            del sys.modules[mod_name]
    return True
