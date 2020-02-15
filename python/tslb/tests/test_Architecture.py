from tslb import Architecture
from tslb.Architecture import architectures
from tslb.Architecture import architectures_reverse


def TestReverse():
    assert len(architectures) == len(architectures_reverse)

    for k, v in architectures.items():
        assert architectures_reverse[v] == k


class TestToInt:
    def test_int(self):
        for i in range(10):
            assert Architecture.to_int(i) == i


    def test_str(self):
        for i in architectures.keys():
            assert Architecture.to_int(architectures[i]) == i


class TestToStr:
    def test_int(self):
        for i in architectures.keys():
            assert Architecture.to_str(i) == architectures[i]

    def test_str(self):
        for s in ['', 'test', 'test2']:
            assert Architecture.to_str(s) == s
