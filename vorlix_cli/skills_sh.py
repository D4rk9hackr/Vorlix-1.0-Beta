"""skills.sh integration — search, install, and publish Vorlix agent skills.

skills.sh (https://skills.sh) is Vercel's open directory for AI agent skills.
This module lets Vorlix tap into the ecosystem: search for community skills,
install them into Vorlix's skills/ directory, and publish your own.

Usage:
  vorlix skills search <query>
  vorlix skills install <github_repo>  # e.g. "vercel-labs/skills" or full URL
  vorlix skills list                    # already works via CLI
  vorlix skills publish <name>          # prepare a skill for skills.sh
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple

# Paths
SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skills")

# GitHub API (no token needed for public repos at low rate limits)
GITHUB_API = "https://api.github.com"
SKILLS_SH_SEARCH = "https://skills.sh/api/skills"


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------

def search_skills_sh(query: str, limit: int = 10) -> List[Dict[str, str]]:
    """Search skills.sh registry for skills matching *query*.

    Falls back to GitHub search if skills.sh API is unreachable.
    """
    results = _search_via_skills_sh(query, limit)
    if results:
        return results
    return _search_via_github(query, limit)


def _search_via_skills_sh(query: str, limit: int) -> List[Dict[str, str]]:
    """Search using skills.sh API."""
    try:
        url = f"{SKILLS_SH_SEARCH}?q={urllib.parse.quote(query)}&limit={limit}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            return [
                {
                    "name": s.get("name", "?"),
                    "description": s.get("description", ""),
                    "source": s.get("repo", ""),
                    "installs": str(s.get("installs", 0)),
                }
                for s in data.get("skills", [])
            ][:limit]
    except Exception:
        return []


def _search_via_github(query: str, limit: int) -> List[Dict[str, str]]:
    """Search GitHub for repos with agent-skills topic or SKILL.md files."""
    results = []
    # Search for repos with SKILL.md in a skills/ directory
    search_url = (
        f"{GITHUB_API}/search/code?q=skills+filename:SKILL.md+repo:&per_page={limit}"
    )
    try:
        req = urllib.request.Request(
            search_url,
            headers={"Accept": "application/vnd.github.v3+json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            for item in data.get("items", []):
                repo_url = item.get("repository", {}).get("full_name", "")
                name = repo_url.split("/")[-1] if repo_url else "?"
                results.append({
                    "name": name,
                    "description": item.get("repository", {}).get("description", "") or "",
                    "source": repo_url,
                    "installs": "—",
                })
    except Exception:
        pass
    return results[:limit]


# ------------------------------------------------------------------
# Install
# ------------------------------------------------------------------

def install_skill(source: str) -> Tuple[bool, str]:
    """Install a skill from a GitHub source into Vorlix's skills/ directory.

    *source* can be:
      - "owner/repo" (GitHub shorthand)
      - "https://github.com/owner/repo" (full URL)
      - "owner/repo/path/to/skill" (specific skill in a monorepo)
    """
    # Parse source
    owner_repo, skill_subdir = _parse_source(source)
    if not owner_repo:
        return False, f"Invalid source: {source}. Use format: owner/repo or owner/repo/path"

    repo_url = f"https://github.com/{owner_repo}.git"
    dest_name = skill_subdir or owner_repo.split("/")[-1]
    dest_path = os.path.join(SKILLS_DIR, dest_name)

    if os.path.exists(dest_path):
        return False, f"Skill '{dest_name}' already exists at {dest_path}"

    # Clone repo to temp dir, copy skill
    tmpdir = tempfile.mkdtemp()
    try:
        # Shallow clone
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, tmpdir],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return False, f"Failed to clone {repo_url}: {result.stderr[:200]}"

        if skill_subdir:
            src = os.path.join(tmpdir, skill_subdir)
        else:
            # Auto-detect: look for skills/ directory or root-level SKILL.md
            skills_subdir = os.path.join(tmpdir, "skills", dest_name)
            if os.path.exists(skills_subdir):
                src = skills_subdir
            elif os.path.exists(os.path.join(tmpdir, "SKILL.md")):
                src = tmpdir  # skill is at repo root
            else:
                # Try to find any SKILL.md
                found = _find_skill_dir(tmpdir)
                if found:
                    src = found
                else:
                    return False, f"No skill found in {repo_url}. Expected a 'skills/' dir or SKILL.md at root."

        # Verify it has SKILL.md
        if not os.path.exists(os.path.join(src, "SKILL.md")):
            return False, f"No SKILL.md found in source."

        # Copy to Vorlix skills dir
        shutil.copytree(src, dest_path, dirs_exist_ok=True)
        return True, f"Installed '{dest_name}' from {owner_repo} → {dest_path}"

    except subprocess.TimeoutExpired:
        return False, f"Clone timed out for {repo_url}"
    except Exception as e:
        return False, str(e)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _parse_source(source: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse a source string into (owner/repo, subdir).

    Examples:
      "vercel-labs/skills" → ("vercel-labs/skills", None)
      "owner/repo/path/to/skill" → ("owner/repo", "path/to/skill")
      "https://github.com/owner/repo.git" → ("owner/repo", None)
    """
    source = source.strip().rstrip("/").rstrip(".git")

    # Full GitHub URL
    gh_match = re.match(r"https?://github\.com/([^/]+/[^/]+)(/.*)?$", source)
    if gh_match:
        return gh_match.group(1), gh_match.group(2)

    # owner/repo/path
    parts = source.split("/")
    if len(parts) >= 2:
        owner_repo = f"{parts[0]}/{parts[1]}"
        subdir = "/".join(parts[2:]) if len(parts) > 2 else None
        return owner_repo, subdir

    return None, None


def _find_skill_dir(base: str) -> Optional[str]:
    """Walk a cloned repo looking for SKILL.md."""
    for root, dirs, files in os.walk(base):
        if "SKILL.md" in files:
            return root
        # Don't descend into .git
        if ".git" in dirs:
            dirs.remove(".git")
    return None


# ------------------------------------------------------------------
# Publish — prepare a Vorlix skill for skills.sh
# ------------------------------------------------------------------

def publish_skill(name: str) -> Tuple[bool, str]:
    """Prepare a Vorlix skill for publishing to skills.sh.

    Checks that the skill has a valid SKILL.md, generates any missing
    metadata, and prints the steps the user needs to take.
    """
    from skills.registry import _read_skill_metadata
    meta = _read_skill_metadata(name)
    if not meta:
        return False, f"Skill '{name}' not found in {SKILLS_DIR}"

    skill_path = os.path.join(SKILLS_DIR, name)

    return True, (
        f"Skill '{name}' is ready for skills.sh.\n\n"
        f"  📂 {skill_path}\n"
        f"  📄 SKILL.md\n"
        f"  🔧 Tools: {', '.join(meta.get('tools', []))}\n"
        f"  📝 {meta.get('description', 'No description')}\n\n"
        f"To publish:\n"
        f"  1. Push this repo to GitHub\n"
        f"  2. Run: npx skills publish\n"
        f"  3. Or manually submit at https://skills.sh\n"
    )


# ------------------------------------------------------------------
# List installed with install source info
# ------------------------------------------------------------------

def list_with_sources() -> List[Dict[str, str]]:
    """List installed skills with metadata."""
    from skills.registry import list_skills, _read_skill_metadata
    skills = []
    for entry in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, entry)
        if os.path.isdir(skill_dir) and not entry.startswith("__"):
            meta = _read_skill_metadata(entry)
            if meta:
                meta["_source"] = "built-in" if os.path.exists(
                    os.path.join(skill_dir, "..", "..", "tiers", f"{entry}_tier.py")
                ) else "community"
                skills.append(meta)
    return skills
