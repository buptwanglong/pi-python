"""
Tests for the Blackboard shared key-value store.
"""

import time

import pytest

from basket_agent.blackboard import Blackboard, BlackboardEntry


class TestBlackboardEntry:
    """Tests for BlackboardEntry."""

    def test_entry_is_frozen(self):
        """BlackboardEntry instances should be immutable."""
        entry = BlackboardEntry(
            key="k", value="v", author="agent-1", timestamp=1.0
        )
        with pytest.raises(Exception):
            entry.key = "new_key"  # type: ignore[misc]

    def test_entry_metadata(self):
        """Entry stores key, value, author, and timestamp."""
        ts = time.time()
        entry = BlackboardEntry(key="foo", value=42, author="explorer", timestamp=ts)
        assert entry.key == "foo"
        assert entry.value == 42
        assert entry.author == "explorer"
        assert entry.timestamp == ts


class TestBlackboard:
    """Tests for the Blackboard immutable store."""

    def test_empty_blackboard(self):
        """A new blackboard has no entries."""
        bb = Blackboard()
        assert bb.keys() == []
        assert bb.read("any") is None
        assert bb.has_key("any") is False

    def test_write_creates_new_blackboard(self):
        """write() returns a new Blackboard; original is untouched."""
        bb = Blackboard()
        new_bb = bb.write("key1", "value1", author="agent-a")

        assert new_bb is not bb
        assert isinstance(new_bb, Blackboard)
        assert new_bb.read("key1") == "value1"

    def test_original_unchanged_after_write(self):
        """The original Blackboard must NOT be mutated by write()."""
        bb = Blackboard()
        _ = bb.write("key1", "value1", author="agent-a")

        assert bb.keys() == []
        assert bb.read("key1") is None

    def test_read_existing_key(self):
        """read() returns the value for an existing key."""
        bb = Blackboard().write("x", 123, author="a")
        assert bb.read("x") == 123

    def test_read_missing_key(self):
        """read() returns None for a non-existent key."""
        bb = Blackboard().write("x", 1, author="a")
        assert bb.read("missing") is None

    def test_overwrite_key(self):
        """Writing the same key replaces the value."""
        bb = Blackboard().write("k", "old", author="a")
        bb2 = bb.write("k", "new", author="b")

        assert bb.read("k") == "old"
        assert bb2.read("k") == "new"

    def test_remove_key(self):
        """remove() returns a new Blackboard without the key."""
        bb = Blackboard().write("a", 1, author="x").write("b", 2, author="x")
        bb2 = bb.remove("a")

        assert bb.has_key("a") is True
        assert bb2.has_key("a") is False
        assert bb2.has_key("b") is True

    def test_remove_nonexistent_key(self):
        """remove() on a missing key returns a new equivalent Blackboard."""
        bb = Blackboard().write("a", 1, author="x")
        bb2 = bb.remove("does_not_exist")
        assert bb2.keys() == ["a"]

    def test_keys_list(self):
        """keys() returns all stored keys."""
        bb = (
            Blackboard()
            .write("alpha", 1, author="a")
            .write("beta", 2, author="b")
            .write("gamma", 3, author="c")
        )
        assert sorted(bb.keys()) == ["alpha", "beta", "gamma"]

    def test_has_key(self):
        """has_key() returns True for existing, False for missing."""
        bb = Blackboard().write("present", "yes", author="a")
        assert bb.has_key("present") is True
        assert bb.has_key("absent") is False

    def test_get_by_author(self):
        """get_by_author() filters entries by their author field."""
        bb = (
            Blackboard()
            .write("k1", "v1", author="alice")
            .write("k2", "v2", author="bob")
            .write("k3", "v3", author="alice")
        )
        alice_entries = bb.get_by_author("alice")
        assert set(alice_entries.keys()) == {"k1", "k3"}

        bob_entries = bb.get_by_author("bob")
        assert set(bob_entries.keys()) == {"k2"}

        nobody = bb.get_by_author("nobody")
        assert nobody == {}

    def test_entry_metadata_via_read_entry(self):
        """read_entry() returns the full BlackboardEntry with metadata."""
        before = time.time()
        bb = Blackboard().write("finding", "critical bug", author="explorer")
        after = time.time()

        entry = bb.read_entry("finding")
        assert entry is not None
        assert entry.key == "finding"
        assert entry.value == "critical bug"
        assert entry.author == "explorer"
        assert before <= entry.timestamp <= after

    def test_read_entry_missing(self):
        """read_entry() returns None for a missing key."""
        bb = Blackboard()
        assert bb.read_entry("nope") is None

    def test_multiple_writes_chain(self):
        """Chained writes produce correct cumulative state."""
        bb = (
            Blackboard()
            .write("a", 1, author="x")
            .write("b", 2, author="y")
            .write("c", 3, author="z")
        )
        assert bb.read("a") == 1
        assert bb.read("b") == 2
        assert bb.read("c") == 3
        assert len(bb.keys()) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
