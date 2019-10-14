class Node(object):
    def __init__(self, data):
        self.data = data
        self.children = []
        self.parents = []

    def __repr__(self):
        return "Node (%s)" % repr(self.data)

    def add_child(self, child):
        if child not in self.children:
            self.children.append(child)
            child.add_parent(self)

    def add_parent(self, parent):
        if parent not in self.parents:
            self.parents.append(parent)
            parent.add_child(self)

    def enumerate(self):
        """
        Does a pre-order traversal to annotate the nodes with numbers.
        """
        nodes = {}

        def traverse(root, number = 0):
            nodes[root] = number

            for child in root.children:
                number = number + 1
                traverse(child, number)

        traverse(self)

        return nodes

def RenderGraphDot(nodes, name):
    dot = "digraph %s {\n" % name

    nodes_enumerated = {}
    number = 0

    for node in nodes:
        nodes_enumerated[node] = number
        number += 1

    for node in nodes_enumerated:
        dot = dot + '%s [label="%s"];\n' % (nodes_enumerated[node], str(node.data))

        for child in node.children:
            dot = dot + "%s -> %s;\n" % (nodes_enumerated[child], nodes_enumerated[node])

    dot = dot + "}\n"

    return dot
