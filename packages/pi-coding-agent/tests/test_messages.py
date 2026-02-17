"""
Tests for message tree structures.
"""

import pytest
from pi_coding_agent.core.messages import MessageTree, MessageTreeNode


@pytest.fixture
def simple_tree_entries():
    """Create simple tree entries for testing."""
    return [
        {
            "id": "root",
            "parent_id": None,
            "timestamp": 1000,
            "type": "message",
            "data": {"content": "Root message"},
        },
        {
            "id": "child1",
            "parent_id": "root",
            "timestamp": 2000,
            "type": "message",
            "data": {"content": "Child 1"},
        },
        {
            "id": "child2",
            "parent_id": "root",
            "timestamp": 3000,
            "type": "message",
            "data": {"content": "Child 2"},
        },
        {
            "id": "grandchild",
            "parent_id": "child1",
            "timestamp": 4000,
            "type": "message",
            "data": {"content": "Grandchild"},
        },
    ]


@pytest.fixture
def branching_tree_entries():
    """Create branching tree entries for testing."""
    return [
        {"id": "1", "parent_id": None, "timestamp": 1000, "type": "message", "data": {}},
        {"id": "2", "parent_id": "1", "timestamp": 2000, "type": "message", "data": {}},
        {"id": "3", "parent_id": "2", "timestamp": 3000, "type": "message", "data": {}},
        {"id": "4", "parent_id": "2", "timestamp": 3500, "type": "message", "data": {}},  # Branch 1
        {"id": "5", "parent_id": "3", "timestamp": 4000, "type": "message", "data": {}},
        {"id": "6", "parent_id": "4", "timestamp": 4500, "type": "message", "data": {}},
    ]


def test_tree_construction(simple_tree_entries):
    """Test basic tree construction."""
    tree = MessageTree(simple_tree_entries)

    assert tree.root is not None
    assert tree.root.id == "root"
    assert len(tree.nodes) == 4


def test_get_node(simple_tree_entries):
    """Test getting a node by ID."""
    tree = MessageTree(simple_tree_entries)

    node = tree.get_node("child1")
    assert node is not None
    assert node.id == "child1"
    assert node.parent_id == "root"

    nonexistent = tree.get_node("nonexistent")
    assert nonexistent is None


def test_parent_child_relationships(simple_tree_entries):
    """Test parent-child relationships are correct."""
    tree = MessageTree(simple_tree_entries)

    root = tree.get_node("root")
    assert len(root.children) == 2

    child1 = tree.get_node("child1")
    assert len(child1.children) == 1
    assert child1.children[0].id == "grandchild"


def test_get_path_to_root(simple_tree_entries):
    """Test getting path from node to root."""
    tree = MessageTree(simple_tree_entries)

    path = tree.get_path_to_root("grandchild")

    assert len(path) == 3
    assert path[0].id == "root"
    assert path[1].id == "child1"
    assert path[2].id == "grandchild"


def test_get_path_to_root_of_root(simple_tree_entries):
    """Test getting path to root of root node."""
    tree = MessageTree(simple_tree_entries)

    path = tree.get_path_to_root("root")

    assert len(path) == 1
    assert path[0].id == "root"


def test_get_branches(branching_tree_entries):
    """Test getting all branches from a node."""
    tree = MessageTree(branching_tree_entries)

    branches = tree.get_branches("2")

    # Should have 2 branches from node "2"
    assert len(branches) >= 2


def test_get_siblings(simple_tree_entries):
    """Test getting sibling nodes."""
    tree = MessageTree(simple_tree_entries)

    siblings = tree.get_siblings("child1")

    assert len(siblings) == 1
    assert siblings[0].id == "child2"


def test_get_siblings_of_root(simple_tree_entries):
    """Test getting siblings of root node."""
    tree = MessageTree(simple_tree_entries)

    siblings = tree.get_siblings("root")

    assert len(siblings) == 0


def test_get_leaf_nodes(simple_tree_entries):
    """Test getting all leaf nodes."""
    tree = MessageTree(simple_tree_entries)

    leaves = tree.get_leaf_nodes()

    assert len(leaves) == 2
    leaf_ids = {leaf.id for leaf in leaves}
    assert "grandchild" in leaf_ids
    assert "child2" in leaf_ids


def test_traverse_preorder(simple_tree_entries):
    """Test pre-order traversal."""
    tree = MessageTree(simple_tree_entries)

    nodes = tree.traverse_preorder()

    assert len(nodes) == 4
    # Root should come first
    assert nodes[0].id == "root"
    # Parent should come before children
    root_idx = next(i for i, n in enumerate(nodes) if n.id == "root")
    child1_idx = next(i for i, n in enumerate(nodes) if n.id == "child1")
    grandchild_idx = next(i for i, n in enumerate(nodes) if n.id == "grandchild")

    assert root_idx < child1_idx < grandchild_idx


def test_traverse_postorder(simple_tree_entries):
    """Test post-order traversal."""
    tree = MessageTree(simple_tree_entries)

    nodes = tree.traverse_postorder()

    assert len(nodes) == 4
    # Root should come last
    assert nodes[-1].id == "root"
    # Children should come before parent
    root_idx = next(i for i, n in enumerate(nodes) if n.id == "root")
    child1_idx = next(i for i, n in enumerate(nodes) if n.id == "child1")
    grandchild_idx = next(i for i, n in enumerate(nodes) if n.id == "grandchild")

    assert grandchild_idx < child1_idx < root_idx


def test_children_sorted_by_timestamp(simple_tree_entries):
    """Test that children are sorted by timestamp."""
    tree = MessageTree(simple_tree_entries)

    root = tree.get_node("root")
    timestamps = [child.timestamp for child in root.children]

    assert timestamps == sorted(timestamps)


def test_empty_tree():
    """Test handling empty tree."""
    tree = MessageTree([])

    assert tree.root is None
    assert len(tree.nodes) == 0
    assert len(tree.get_leaf_nodes()) == 0


def test_single_node_tree():
    """Test tree with single node."""
    entries = [
        {"id": "only", "parent_id": None, "timestamp": 1000, "type": "message", "data": {}}
    ]

    tree = MessageTree(entries)

    assert tree.root is not None
    assert tree.root.id == "only"
    assert len(tree.root.children) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
