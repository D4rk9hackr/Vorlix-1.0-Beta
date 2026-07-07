"""Unit tests for skills registry."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.registry import list_skills, activate_skill, deactivate_skill


class TestSkillsRegistry:
    def test_list_skills_returns_list(self):
        skills = list_skills()
        assert isinstance(skills, list), f"Expected list, got {type(skills)}"

    def test_list_skills_contains_known_skills(self):
        skills = list_skills()
        names = [s["name"] for s in skills]
        # We should at least have time_reminders (from the zip)
        known_skills = {"time_reminders", "terminal", "system_query", "browser_bridge", "computer_vision"}
        found = [s for s in known_skills if s in names]
        assert len(found) > 0, f"No known skills found in {names}"

    def test_list_skills_metadata_structure(self):
        skills = list_skills()
        for s in skills:
            assert "name" in s, f"Skill missing 'name': {s}"
            assert "tools" in s, f"Skill missing 'tools': {s}"
            assert isinstance(s["tools"], list), f"Skill 'tools' not a list: {s}"

    def test_activate_skill_time_reminders(self):
        success, msg, tier = activate_skill("time_reminders")
        assert success, f"Failed to activate time_reminders: {msg}"
        assert tier is not None, "Expected a tier instance"
        assert tier.name == "TimeRemindersTier", f"Expected TimeRemindersTier, got {tier.name}"

    def test_activate_skill_unknown(self):
        success, msg, tier = activate_skill("nonexistent_skill_xyz")
        assert not success, "Should not activate nonexistent skill"
        assert tier is None, "Should not return a tier for nonexistent skill"

    def test_deactivate_skill(self):
        # Activate then deactivate
        activate_skill("time_reminders")
        result = deactivate_skill("time_reminders")
        assert result, "deactivate_skill should return True"
