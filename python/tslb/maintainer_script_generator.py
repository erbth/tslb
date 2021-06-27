"""
Generate single maintainer scripts out of sets of maintainer scripts.
Essentially this is a reducer for the various maintainer script parts created
while the package flows through the build pipeline.
"""
from dataclasses import dataclass
import re


# eq=False to efficiently compare and hash unique instances by id.
@dataclass(frozen=True, eq=False)
class MaintainerScript:
    """
    shebang must be the entire shebang (but without trailing newline)
    shebang == None indicates a binary like an ELF-executable.

    text must include the shebang as first line and have any
    script-definition-header removed.
    """
    script_id: str
    before: str
    after: str
    shebang: str
    text: str

    @property
    def interpreter(self):
        if self.shebang is not None:
            return re.match(r'^#!(\S*).*$', self.shebang)[1]
        else:
            return None


class MaintainerScriptGenerator:
    def __init__(self):
        self._scripts = []

    @staticmethod
    def _test_exit0_compatible(text):
        last_line_found = False

        for line in reversed(text.split('\n')):
            line = line.strip()
            if not line:
                continue

            if not last_line_found:
                if not re.match(r'^\s*exit\s+0\s*$', line):
                    return False

                last_line_found = True

            else:
                line = re.sub(r'#.*', '', line)
                if re.match(r'^.*exit\s+0(\s.*)?$', line):
                    return False

        return True


    def add_script(self, script):
        """
        :type script: MaintainerScript
        :raises ValueError: If the resulting set of maintainer scripts would
            not be collatable.
        """
        if self._scripts:
            # If there are already scripts, ensure that the set stays
            # collatable when the new one is added.
            # To be collatable all scripts in a set must share exactly the same
            # shebang (i.e. same parameters to the interpreter), use bash and
            # end with 'exit 0'. Moreover they must not use 'exit 0' somewhere
            # else.
            if self._scripts[0].interpreter != "/bin/bash" and \
                    self._scripts[0].interpreter != "/usr/bin/bash":
                raise ValueError("All maintainer scripts in a set with more than one script must "
                        "use bash as interpreter.")

            if script.shebang != self._scripts[0].shebang:
                raise ValueError("All maintainer scripts in a set with more than one script must "
                        "share exactly the same shebang.")

            if not self._test_exit0_compatible(self._scripts[0].text):
                raise ValueError("All maintainer scripts in a set must use 'exit 0' exactly as last line. "
                        "The one contained already does not.")

            if not self._test_exit0_compatible(script.text):
                raise ValueError("All maintainer scripts in a set must use 'exit 0' exactly as last line. "
                        "The one to add does not.")

        self._scripts.append(script)


    def collate_scripts(self):
        """
        :raises CollateError: If collating failed.
        """
        if not self._scripts:
            return None

        if len(self._scripts) == 1:
            return self._scripts[0].text


        # Non-trivial case.
        # Build graph of scripts
        G = self._build_graph(self._scripts)

        # Connect the graph if it is not connected
        self._connect_graph(G)

        # Ensure that it is cycle-free
        self._ensure_cycle_freeness(G)

        # Compute topological sorting
        order = self._compute_topological_order(G)

        # Concatenate scripts, stripping of the shebang and trailing 'exit 0'.
        # Then surround the collated script by them.
        collated = [order[0].shebang]
        exit_statement = None
        for script in order:
            lines = script.text.split('\n')
            while not lines[-1].strip():
                lines.pop()

            collated += lines[1:-1]
            exit_statement = lines[-1]

        collated.append(exit_statement)

        return '\n'.join(collated)


    @staticmethod
    def _build_graph(scripts):
        # Adjacency lists
        G = { v: [] for v in scripts }

        # Add edges
        id_node_map = { s.script_id: s for s in scripts }
        for v in G:
            for u_ in v.before:
                try:
                    u = id_node_map[u_]
                    if u not in G[v]:
                        G[v].append(u)

                except KeyError as e:
                    raise CollateError("Script `%s' references script `%s', which does not exist." %
                            (v.script_id, u_)) from e

            for w_ in v.after:
                try:
                    w = id_node_map[w_]
                    if v not in G[w]:
                        G[w].append(v)

                except KeyError as e:
                    raise CollateError("Script `%s' references script `%s', which does not exist." %
                            (v.script_id, w_)) from e

        return G

    @staticmethod
    def _format_graph(G):
        s = '{\n'
        for v in G:
            s += '    %s: [' % v.script_id + ', '.join(u.script_id for u in G[v]) + '],\n'

        return s + '}'


    @staticmethod
    def _connect_graph(G):
        # Classical union-find approach 
        # Initially, every node is in its own cc.
        parent = { v: v for v in G }

        def find(v):
            if parent[v] == v:
                return v
            else:
                u = find(parent[v])
                parent[v] = u
                return u

        def union(u, v):
            r1 = find(u)
            r2 = find(v)
            if r1 != r2:
                parent[r1] = r2

        # Traverse graph and unite ccs if edges between them are disovered.
        for v in G:
            for u in G[v]:
                if find(u) != find(v):
                    union(u, v)

        # Enumerate all ccs left
        ccs = {v: [] for v in G if find(v) == v}
        for v in G:
            ccs[find(v)].append(v)

        ccs = ccs.values()

        # Connect ccs
        attachment_point = None
        for cc in ccs:
            roots = set(cc)
            no_outgoing = set(cc)
            for v in cc:
                for u in G[v]:
                    roots.discard(u)
                    no_outgoing.discard(v)

            if not roots:
                raise CollateError("The connected component with node `%s' has no root -> cycle." %
                        cc[0].script_id)

            if not no_outgoing:
                raise CollateError("Every node in the connected component with node `%s' has outgoing "
                        "edges -> cycle." % cc[0].script_id)

            if attachment_point:
                G[attachment_point].append(next(iter(roots)))

            attachment_point = next(iter(no_outgoing))


    @staticmethod
    def _ensure_cycle_freeness(G):
        # DFS with on-stack tracking to find backwards edges
        stack = []
        on_stack = set()
        visited = set()

        # Identify root nodes with no incoming edges
        roots = set(G.keys())
        for v in G:
            for u in G[v]:
                roots.discard(u)

        # If there is no such root, there must be a cycle...
        if not roots:
            raise CollateError("There is no node which is not part of a cycle.")

        def visit(v):
            # Well having two stacks - the one here and the implicit call stack
            # - is bad. But recursion is easy to use and printing cycles
            # helpful.
            stack.append(v)
            on_stack.add(v)
            visited.add(v)

            for u in G[v]:
                if u in on_stack:
                    cycle = [u.script_id]
                    i = len(stack) - 1
                    while i >= 0:
                        cycle.append(stack[i].script_id)
                        if stack[i] == u:
                            break

                    raise CollateError("Found a cycle: %s." % ' <- '.join(cycle))

                if u in visited:
                    continue

                visit(u)

            on_stack.remove(v)
            stack.pop()

        for r in roots:
            if r not in visited:
                visit(r)


    @staticmethod
    def _compute_topological_order(G):
        output = []

        # FIFO / count of incomming paths processed approach
        roots = set(G.keys())
        for v in G:
            for u in G[v]:
                roots.discard(u)

        queue = list(roots)

        unvisited_edges = { v: 0 for v in G }
        for v in G:
            for u in G[v]:
                unvisited_edges[u] += 1

        while len(queue) > 0:
            v = queue[0]
            queue = queue[1:]
            output.append(v)

            for u in G[v]:
                unvisited_edges[u] -= 1
                if unvisited_edges[u] == 0:
                    queue.append(u)

        return output


#********************************** Exceptions ********************************
class CollateError(Exception):
    pass
