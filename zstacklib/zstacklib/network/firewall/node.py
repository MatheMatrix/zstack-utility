"""Base tree node structure for iptables rule management."""

from typing import Optional, List, Callable, Any


class Node:
    """Tree structure base class for iptables elements.
    
    Provides methods for tree traversal, searching, and manipulation.
    Used as base class for IPTableTable, IPTableChain, IPTableRule.
    """
    
    def __init__(self):
        """Init."""
        self.name: Optional[str] = None
        self.identity: Optional[str] = None
        self.parent: Optional['Node'] = None
        self.children: List['Node'] = []

    def add_child(self, node: 'Node') -> None:
        """Add child."""
        self.children.append(node)
        node.parent = self

    def get_child_by_name(self, name: str) -> Optional['Node']:
        """Get child by name."""
        for c in self.children:
            if c.name == name:
                return c
        return None

    def get_child_by_identity(self, identity: str) -> Optional['Node']:
        """Get child by identity."""
        for c in self.children:
            if c.identity == identity:
                return c
        return None

    def insert_child_before(self, n1: 'Node', n2: 'Node') -> None:
        """Insert child before."""
        pos = self.children.index(n1)
        self.children.insert(pos, n2)
        n2.parent = self

    def insert_child_after(self, n1: 'Node', n2: 'Node') -> None:
        """Insert child after."""
        pos = self.children.index(n1)
        self.children.insert(pos + 1, n2)
        n2.parent = self

    def insert_child_all_after_by_name(self, name: str, node: 'Node') -> None:
        """Insert child all after by name."""
        n = self.search_by_name(name)
        if not n:
            raise ValueError('cannot find node[name:%s]' % name)
        n.parent.insert_child_after(n, node)

    def insert_child_all_after_by_identity(self, identity: str, node: 'Node') -> None:
        """Insert child all after by identity."""
        n = self.search_by_identity(identity)
        if not n:
            raise ValueError('cannot find node[identity:%s]' % identity)
        n.parent.insert_child_after(n, node)

    def insert_child_all_before_by_name(self, name: str, node: 'Node') -> None:
        """Insert child all before by name."""
        n = self.search_by_name(name)
        if not n:
            raise ValueError('cannot find node[name:%s]' % name)
        n.parent.insert_child_before(n, node)

    def insert_child_all_before_by_identity(self, identity: str, node: 'Node') -> None:
        """Insert child all before by identity."""
        n = self.search_by_identity(identity)
        if not n:
            raise ValueError('cannot find node[identity:%s]' % identity)
        n.parent.insert_child_before(n, node)

    def delete_child_by_name(self, name: str) -> None:
        """Delete child by name."""
        c = self.get_child_by_name(name)
        if c:
            self.children.remove(c)
            c.parent = None

    def delete_child_by_identity(self, identity: str) -> None:
        """Delete child by identity."""
        c = self.get_child_by_identity(identity)
        if c:
            self.children.remove(c)
            c.parent = None

    def walk(self, callback: Callable[['Node', Any], bool], data: Any = None) -> Optional['Node']:
        """Walk."""
        def do_walk(node: 'Node') -> Optional['Node']:
            """Do walk."""
            if callback(node, data):
                return node
            for n in node.children:
                ret = do_walk(n)
                if ret:
                    return ret
            return None
        return do_walk(self)

    def walk_all(self, callback: Callable[['Node', Any], bool], data: Any = None) -> List['Node']:
        """Walk all."""
        ret: List['Node'] = []
        
        def do_walk_all(node: 'Node') -> None:
            """Do walk all."""
            if callback(node, data):
                ret.append(node)
            for n in node.children:
                do_walk_all(n)
        
        do_walk_all(self)
        return ret

    def search_by_name(self, name: str) -> Optional['Node']:
        """Search by name."""
        return self.walk(lambda n, u: n.name == name, None)

    def search_by_identity(self, identity: str) -> Optional['Node']:
        """Search by identity."""
        return self.walk(lambda n, u: n.identity == identity, None)

    def search_all_by_name(self, name: str) -> List['Node']:
        """Search all by name."""
        return self.walk_all(lambda n, u: n.name == name, None)

    def search_all_by_identity(self, identity: str) -> List['Node']:
        """Search all by identity."""
        return self.walk_all(lambda n, u: n.identity == identity, None)

    def delete_all_by_name(self, name: str) -> None:
        """Delete all by name."""
        lst = self.search_all_by_name(name)
        for l in lst:
            l.delete()

    def delete_all_by_identity(self, identity: str) -> None:
        """Delete all by identity."""
        lst = self.search_all_by_identity(identity)
        for l in lst:
            l.delete()

    def delete(self) -> None:
        """Delete."""
        if self.parent:
            self.parent.children.remove(self)
            self.parent = None

    def __str__(self) -> str:
        """Str."""
        return self.identity or ''
