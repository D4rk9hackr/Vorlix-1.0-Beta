"""Unit tests for FileIOTier — file.read and file.patch."""
import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tier_base import TierRequest, TierResult
from tiers.file_io_tier import FileIOTier, BLOCKED_PATH_PARTS


class TestFileIOTier:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tier = FileIOTier(project_dir=self.tmpdir)
        self.test_file = os.path.join(self.tmpdir, "test.txt")
        with open(self.test_file, "w") as f:
            f.write("hello world\nline 2\nline 3\n")

    def teardown_method(self):
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)

    # --- file.read tests ---

    def test_read_success(self):
        req = TierRequest(
            tool="file.read",
            arguments={"path": "test.txt"},
            reasoning="Testing file read.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.SUCCESS
        assert "hello world" in result.data["content"]
        assert result.data["total_lines"] == 3
        assert result.data["returned_lines"] == 3
        assert result.data["truncated"] is False

    def test_read_nonexistent_file(self):
        req = TierRequest(
            tool="file.read",
            arguments={"path": "nope.txt"},
            reasoning="Testing nonexistent file.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED
        assert "not found" in result.message

    def test_read_outside_project_dir(self):
        req = TierRequest(
            tool="file.read",
            arguments={"path": "/etc/passwd"},
            reasoning="Testing blocked path.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED
        assert "guardrails" in result.message

    def test_read_secrets_location(self):
        req = TierRequest(
            tool="file.read",
            arguments={"path": os.path.expanduser("~/.ssh/config")},
            reasoning="Testing secrets block.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED

    def test_read_max_lines_truncation(self):
        long_path = os.path.join(self.tmpdir, "long.txt")
        with open(long_path, "w") as f:
            for i in range(500):
                f.write(f"line {i}\n")
        req = TierRequest(
            tool="file.read",
            arguments={"path": "long.txt", "max_lines": 10},
            reasoning="Testing truncation.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.SUCCESS
        assert result.data["returned_lines"] == 10
        assert result.data["truncated"] is True
        assert result.data["total_lines"] == 500

    def test_read_empty_path(self):
        req = TierRequest(
            tool="file.read",
            arguments={"path": ""},
            reasoning="Testing empty path.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED
        assert "No path" in result.message

    # --- file.patch tests ---

    def test_patch_success(self):
        req = TierRequest(
            tool="file.patch",
            arguments={
                "path": "test.txt",
                "old_content": "hello world",
                "new_content": "hello patched",
            },
            reasoning="Testing file patch.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.SUCCESS
        assert "Patch applied" in result.message
        with open(self.test_file) as f:
            content = f.read()
        assert "hello patched" in content
        assert "line 2" in content

    def test_patch_old_content_not_found(self):
        req = TierRequest(
            tool="file.patch",
            arguments={
                "path": "test.txt",
                "old_content": "does not exist",
                "new_content": "replacement",
            },
            reasoning="Testing patch with nonexistent content.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED
        assert "not found" in result.message

    def test_patch_ambiguous_old_content(self):
        path = os.path.join(self.tmpdir, "dup.txt")
        with open(path, "w") as f:
            f.write("repeat\nmiddle\nrepeat\n")
        req = TierRequest(
            tool="file.patch",
            arguments={
                "path": "dup.txt",
                "old_content": "repeat",
                "new_content": "changed",
            },
            reasoning="Testing ambiguous patch.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED
        assert "ambiguous" in result.message

    def test_patch_under_human_override(self):
        self.tier._human_override.freeze()
        req = TierRequest(
            tool="file.patch",
            arguments={
                "path": "test.txt",
                "old_content": "hello world",
                "new_content": "hello patched",
            },
            reasoning="Testing patch blocked by override.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED
        assert "Human override" in result.message
        self.tier._human_override.resume()

    def test_patch_logs_to_memory(self):
        req = TierRequest(
            tool="file.patch",
            arguments={
                "path": "test.txt",
                "old_content": "hello world",
                "new_content": "hello logged",
            },
            reasoning="Memory logging test.",
            confidence=0.95,
        )
        asyncio.run(self.tier.execute(req))
        memory = self.tier._ledger.read_memory()
        assert "Applying patch to" in memory
        assert "test.txt" in memory
        assert "-hello world" in memory or "hello world" in memory

    def test_patch_outside_project_dir(self):
        req = TierRequest(
            tool="file.patch",
            arguments={
                "path": "/etc/hostname",
                "old_content": "old",
                "new_content": "new",
            },
            reasoning="Testing blocked path for patch.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED
        assert "guardrails" in result.message

    def test_patch_missing_args(self):
        req = TierRequest(
            tool="file.patch",
            arguments={"path": "test.txt"},
            reasoning="Missing args test.",
            confidence=0.95,
        )
        result = asyncio.run(self.tier.execute(req))
        assert result.result == TierResult.BLOCKED


class TestFileIOTierGuardrails:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.tier = FileIOTier(project_dir=self.tmpdir)

    def teardown_method(self):
        os.rmdir(self.tmpdir)

    def test_guardrails_block_unknown_tool(self):
        req = TierRequest(
            tool="unknown.tool",
            arguments={},
            reasoning="Test guardrails pass through.",
            confidence=0.95,
        )
        assert self.tier.is_within_guardrails(req) is True

    def test_guardrails_block_outside_path(self):
        req = TierRequest(
            tool="file.read",
            arguments={"path": "/etc/passwd"},
            reasoning="Test blocked path.",
            confidence=0.95,
        )
        assert self.tier.is_within_guardrails(req) is False

    def test_guardrails_allow_inside_path(self):
        req = TierRequest(
            tool="file.read",
            arguments={"path": "test.txt"},
            reasoning="Test allowed path.",
            confidence=0.95,
        )
        assert self.tier.is_within_guardrails(req) is True


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
