"""Tests for skills.sh integration module."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vorlix_cli.skills_sh import (
    _parse_source,
    _find_skill_dir,
    publish_skill,
    list_with_sources,
)


class TestParseSource:
    def test_owner_repo(self):
        owner_repo, subdir = _parse_source("vercel-labs/skills")
        assert owner_repo == "vercel-labs/skills"
        assert subdir is None

    def test_owner_repo_subdir(self):
        owner_repo, subdir = _parse_source("owner/repo/path/to/skill")
        assert owner_repo == "owner/repo"
        assert subdir == "path/to/skill"

    def test_full_github_url(self):
        owner_repo, subdir = _parse_source("https://github.com/vercel-labs/skills.git")
        assert owner_repo == "vercel-labs/skills"
        assert subdir is None

    def test_full_url_with_path(self):
        owner_repo, subdir = _parse_source("https://github.com/owner/repo/tree/main/skills/foo")
        assert owner_repo == "owner/repo"
        assert subdir is not None

    def test_invalid_source(self):
        owner_repo, subdir = _parse_source("notavalidurl")
        assert owner_repo is None
        assert subdir is None


class TestFindSkillDir:
    def test_finds_skil_md_in_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            skil_path = os.path.join(tmp, "SKILL.md")
            with open(skil_path, "w") as f:
                f.write("# Test Skill")
            result = _find_skill_dir(tmp)
            assert result == tmp

    def test_finds_skil_md_in_nested_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = os.path.join(tmp, "skills", "myskill")
            os.makedirs(nested)
            skil_path = os.path.join(nested, "SKILL.md")
            with open(skil_path, "w") as f:
                f.write("# Test Skill")
            result = _find_skill_dir(tmp)
            assert result == nested

    def test_returns_none_when_no_skill_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _find_skill_dir(tmp)
            assert result is None


class TestPublishSkill:
    def test_publish_nonexistent_skill(self):
        success, msg = publish_skill("nonexistent_skill_xyz")
        assert not success

    def test_publish_existing_skill(self):
        success, msg = publish_skill("time_reminders")
        assert success


class TestListWithSources:
    def test_returns_list(self):
        skills = list_with_sources()
        assert isinstance(skills, list)

    def test_skills_have_source_key(self):
        skills = list_with_sources()
        if skills:
            assert "_source" in skills[0]
