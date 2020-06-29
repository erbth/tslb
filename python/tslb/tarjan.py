"""
An implementation of Tarjan's strongly connected components algorithm.
"""
from .stack import stack


def find_scc(G):
    """
    Maps nodes to SCCs using Tarjan's strongly connected components algorithm.
    This implementation relies on hash tables (python dicts) to find a node's
    adjacency list and does therefore exceed the algorithm's deterministic
    running time bounds.

    :param dict(str, list(str)) G: A graph in adjacency list representation
    :returns tuple(dict(str, int), int): (scc-map, count of sccs)
    """
    LOWPT = {}
    LOWVINE = {}
    NUMBER = {n: None for n in G.keys()}

    ONDFSSTACK = {n: False for n in G.keys()}
    ONSTACK = {n: False for n in G.keys()}

    i = 0

    working_stack = stack()

    j = 0
    SCC = {n: None for n in G.keys()}

    def STRONGCONNECT(v):
        nonlocal i, j

        LOWPT[v] = i
        LOWVINE[v] = i
        NUMBER[v] = i
        i += 1

        ONDFSSTACK[v] = True

        working_stack.push(v)
        ONSTACK[v] = True

        for w in G[v]:
            if NUMBER[w] is None:  # tree arc
                STRONGCONNECT(w)
                LOWPT[v] = min(LOWPT[v], LOWPT[w])
                LOWVINE[v] = min(LOWVINE[v], LOWVINE[w])
            elif ONDFSSTACK[w]:  # frond
                LOWPT[v] = min(LOWPT[v], NUMBER[w])
            elif NUMBER[w] < NUMBER[v]:  # vine
                if ONSTACK[w]:
                    LOWVINE[v] = min(LOWVINE[v], NUMBER[w])

        if LOWPT[v] == NUMBER[v] and LOWVINE[v] == NUMBER[v]:
            while not working_stack.empty and NUMBER[working_stack.top] >= NUMBER[v]:
                ONSTACK[working_stack.top] = False
                SCC[working_stack.pop()] = j

            j += 1

        ONDFSSTACK[v] = False


    for w in G.keys():
        if NUMBER[w] is None:
            STRONGCONNECT(w)


    return (SCC, j)
