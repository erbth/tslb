from ..tarjan import find_scc


class Test_find_scc:
    def test_case_1(self):
        """
        From Tarjan's original paper
        """
        G = {
            1: [2],
            2: [3, 8],
            3: [7, 4],
            4: [5],
            5: [3, 6],
            6: [],
            7: [4, 6],
            8: [1, 7]
        }

        scc, j = find_scc(G)
        assert j == 3
        assert scc == {
            6: 0,
            3: 1,
            7: 1,
            4: 1,
            5: 1,
            1: 2,
            2: 2,
            8: 2
        }


    def test_case_2(self):
        G = {
            'a': ['c', 'm'],
            'c': ['b', 'e'],
            'b': ['a', 'd'],
            'd': ['g', 'e', 'h'],
            'g': [],
            'e': ['f', 'd', 'i'],
            'f': [],
            'h': ['k'],
            'i': ['j'],
            'j': ['h'],
            'k': ['j', 'l'],
            'l': ['i'],
            'm': ['n', 'p'],
            'n': ['o'],
            'o': ['m'],
            'p': ['q'],
            'q': ['n']
        }

        scc, j = find_scc(G)
        assert j == 6
        assert scc == {
            'g': 0,
            'f': 1,
            'a': 5,
            'b': 5,
            'c': 5,
            'd': 3,
            'e': 3,
            'h': 2,
            'i': 2,
            'j': 2,
            'k': 2,
            'l': 2,
            'm': 4,
            'n': 4,
            'o': 4,
            'p': 4,
            'q': 4
        }
