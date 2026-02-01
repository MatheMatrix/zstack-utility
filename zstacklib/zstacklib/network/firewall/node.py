"""Base tree node structure for iptables rule management."""

from typing import Optional, List, Callable, Any


class Node:
    """Tree structure base class for iptables elements.
    
    Provides methods for tree traversal, searching, and manipulation.
    Used as base class for IPTableTable, IPTableChain, IPTableRule.
    """
    
    def __init__(self):
        self.name: Optional[str] = None
        self.identity: Optional[str] = None
        self.parent: Optional['Node'] = None
        self.children: List['Node'] = []

    def add_child(self, node: 'Node') -> None:
        self.children.append(node)
        node.parent = self

    def get_child_by_name(self, name: str) -> Optional['Node']:
        for c in self.children:
            if c.name == name:
                return c
        return None

    def get_child_by_identity(self, identity: str) -> Optional['Node']:
        for c in self.children:
            if c.identity == identity:
                return c
        return None

    def insert_child_before(self, n1: 'Node', n2: 'Node') -> None:
        pos = self.children.index(n1)
        self.children.insert(pos - 1, n2)
        n2.parent = self

    def insert_child_after(self, n1: 'Node', n2: 'Node') -> None:
        pos = self.children.index(n1)
        self.children.insert(pos + 1, n2)
        n2.parent = self

    def insert_child_all_after_by_name(self, name: str, node: 'Node') -> None:
        n = self.search_by_name(name)
        if not n:
            raise ValueError('cannot find node[name:%s]' % name)
        n.parent.insert_child_after(n, node)

    def insert_child_all_after_by_identity(self, identity: str, node: 'Node') -> None:
        n = self.search_by_identity(identity)
        if not n:
            raise ValueError('cannot find node[identity:%s]' % identity)
        n.parent.insert_child_after(n, node)

    def insert_child_all_before_by_name(self, name: str, node: 'Node') -> None:
        n = self.search_by_name(name)
        if not n:
            raise ValueError('cannot find node[name:%s]' % name)
        n.parent.insert_child_before(n, node)

    def insert_child_all_before_by_identity(self, identity: str, node: 'Node') -> None:
        n = self.search_by_identity(identity)
        if not n:
            raise ValueError('cannot find node[identity:%s]' % identity)
        n.parent.insert_child_before(n, node)

    def delete_child_by_name(self, name: str) -> None:
        c = self.get_child_by_name(name)
        if c:
            self.children.remove(c)
            c.parent = None

    def delete_child_by_identity(self, identity: str) -> None:
        c = self.get_child_by_identity(identity)
        if c:
            self.children.remove(c)
            c.parent = None

    def walk(self, callback: Callable[['Node', Any], bool], data: Any = None) -> Optional['Node']:
        def do_walk(node: 'Node') -> Optional['Node']:
            if callback(node, data):
                return node
            for n in node.children:
                ret = do_walk(n)
                if ret:
                    return ret
            return None
        return do_walk(self)

    def walk_all(self, callback: Callable[['Node', Any], bool], data: Any = None) -> List['Node']:
        ret: List['Node'] = []
        
        def do_walk_all(node: 'Node') -> None:
            if callback(node, data):
                ret.append(node)
            for n in node.children:
                do_walk_all(n)
        
        do_walk_all(self)
        return ret

    def search_by_name(self, name: str) -> Optional['Node']:
        return self.walk(lambda n, u: n.name == name, None)

    def search_by_identity(self, identity: str) -> Optional['Node']:
        return self.walk(lambda n, u: n.identity == identity, None)

    def search_all_by_name(self, name: str) -> List['Node']:
        return self.walk_all(lambda n, u: n.name == name, None)

    def search_all_by_identity(self, identity: str) -> List['Node']:
        return self.walk_all(lambda n, u: n.identity == identity, None)

    def delete_all_by_name(self, name: str) -> None:
        lst = self.search_all_by_name(name)
        for l in lst:
            l.delete()

    def delete_all_by_identity(self, identity: str) -> None:
        lst = self.search_all_by_identity(identity)
        for l in lst:
            l.delete()

    def delete(self) -> None:
        if self.parent:
            self.parent.children.remove(self)
            self.parent = None

    def __str__(self) -> str:
        return self.identity or ''
