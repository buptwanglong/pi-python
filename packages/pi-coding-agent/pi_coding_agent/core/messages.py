"""
Message tree structures for session navigation.

Handles building and navigating tree structures from flat JSONL entries.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class MessageTreeNode(BaseModel):
    """A node in the message tree."""

    id: str
    parent_id: Optional[str]
    timestamp: int
    type: str
    data: Dict[str, Any]
    children: List["MessageTreeNode"] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class MessageTree:
    """
    Message tree for navigating conversation branches.

    Builds a tree structure from flat JSONL entries with parent_id references.
    """

    def __init__(self, entries: List[Dict[str, Any]]):
        """
        Build a tree from entries.

        Args:
            entries: List of entry dictionaries (from SessionEntry.model_dump())
        """
        self.entries = entries
        self.nodes: Dict[str, MessageTreeNode] = {}
        self.root: Optional[MessageTreeNode] = None

        self._build_tree()

    def _build_tree(self) -> None:
        """Build the tree structure from entries."""
        # Create all nodes first
        for entry in self.entries:
            node = MessageTreeNode(
                id=entry["id"],
                parent_id=entry.get("parent_id"),
                timestamp=entry["timestamp"],
                type=entry["type"],
                data=entry.get("data", {}),
            )
            self.nodes[node.id] = node

        # Build parent-child relationships
        for node in self.nodes.values():
            if node.parent_id is None:
                # Root node (or multiple roots)
                if self.root is None:
                    self.root = node
            elif node.parent_id in self.nodes:
                parent = self.nodes[node.parent_id]
                parent.children.append(node)

        # Sort children by timestamp
        for node in self.nodes.values():
            node.children.sort(key=lambda n: n.timestamp)

    def get_node(self, node_id: str) -> Optional[MessageTreeNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_path_to_root(self, node_id: str) -> List[MessageTreeNode]:
        """
        Get the path from a node to the root.

        Args:
            node_id: Node ID

        Returns:
            List of nodes from root to the specified node
        """
        path = []
        current = self.nodes.get(node_id)

        while current:
            path.append(current)
            if current.parent_id:
                current = self.nodes.get(current.parent_id)
            else:
                break

        return list(reversed(path))

    def get_branches(self, node_id: str) -> List[List[MessageTreeNode]]:
        """
        Get all branches from a node.

        Args:
            node_id: Node ID

        Returns:
            List of branches, where each branch is a list of nodes
        """
        node = self.nodes.get(node_id)
        if not node:
            return []

        if not node.children:
            return [[node]]

        branches = []
        for child in node.children:
            child_branches = self.get_branches(child.id)
            for branch in child_branches:
                branches.append([node] + branch)

        return branches

    def get_siblings(self, node_id: str) -> List[MessageTreeNode]:
        """
        Get sibling nodes (nodes with the same parent).

        Args:
            node_id: Node ID

        Returns:
            List of sibling nodes (excluding the node itself)
        """
        node = self.nodes.get(node_id)
        if not node or not node.parent_id:
            return []

        parent = self.nodes.get(node.parent_id)
        if not parent:
            return []

        return [child for child in parent.children if child.id != node_id]

    def get_leaf_nodes(self) -> List[MessageTreeNode]:
        """
        Get all leaf nodes (nodes with no children).

        Returns:
            List of leaf nodes
        """
        return [node for node in self.nodes.values() if not node.children]

    def traverse_preorder(self) -> List[MessageTreeNode]:
        """
        Traverse the tree in pre-order (parent before children).

        Returns:
            List of nodes in pre-order
        """
        if not self.root:
            return []

        result = []

        def _traverse(node: MessageTreeNode) -> None:
            result.append(node)
            for child in node.children:
                _traverse(child)

        _traverse(self.root)
        return result

    def traverse_postorder(self) -> List[MessageTreeNode]:
        """
        Traverse the tree in post-order (children before parent).

        Returns:
            List of nodes in post-order
        """
        if not self.root:
            return []

        result = []

        def _traverse(node: MessageTreeNode) -> None:
            for child in node.children:
                _traverse(child)
            result.append(node)

        _traverse(self.root)
        return result


__all__ = ["MessageTreeNode", "MessageTree"]
