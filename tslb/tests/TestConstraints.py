import unittest
from Constraint import *

class TestDependencyList(unittest.TestCase):
    def test_add_empty(self):
        dl = DependencyList()
        self.assertEqual(dl.l, {})

        dl.add_constraint(VersionConstraint(">", "2"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint(">", "2") ]})

    def test_constrain_upper(self):
        dl = DependencyList()
        self.assertEqual(dl.l, {})

        dl.add_constraint(VersionConstraint(">=", "2"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint(">=", "2") ]})

        dl.add_constraint(VersionConstraint("", "3"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint(">=", "2") ]})

        dl.add_constraint(VersionConstraint(">", "2"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint(">", "2") ]})

        dl.add_constraint(VersionConstraint(">=", "3"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint(">=", "3") ]})

        dl.add_constraint(VersionConstraint("!=", "3"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint(">", "3") ]})

        dl.add_constraint(VersionConstraint("=", "3.1"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint("=", "3.1") ]})

    def test_costrain_lower(self):
        dl = DependencyList()
        self.assertEqual(dl.l, {})

        dl.add_constraint(VersionConstraint("<=", "2"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint("<=", "2") ]})

        dl.add_constraint(VersionConstraint("", "1"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint("<=", "2") ]})

        dl.add_constraint(VersionConstraint("<", "2"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint("<", "2") ]})

        dl.add_constraint(VersionConstraint("<=", "1"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint("<=", "1") ]})

        dl.add_constraint(VersionConstraint("!=", "1"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint("<", "1") ]})

        dl.add_constraint(VersionConstraint("=", "0.9"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint("=", "0.9") ]})

    def test_constrain_interval(self):
        dl = DependencyList()
        self.assertEqual(dl.l, {})

        dl.add_constraint(VersionConstraint(">=", "2"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint(">=", "2") ]})

        dl.add_constraint(VersionConstraint("<", "4"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint(">=", "2"), VersionConstraint("<", "4") ]})

        dl.add_constraint(VersionConstraint("<=", "2"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint("=", "2") ]})

    def test_contradiction(self):
        dl = DependencyList()
        self.assertEqual(dl.l, {})

        dl.add_constraint(VersionConstraint(">=", "2"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint(">=", "2") ]})

        self.assertRaises(ConstraintContradiction, dl.add_constraint, VersionConstraint("<", "2"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint(">=", "2") ]})

        self.assertRaises(ConstraintContradiction, dl.add_constraint, VersionConstraint("=", "1"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint(">=", "2") ]})

    def test_contains(self):
        dl = DependencyList()
        self.assertEqual(dl.l, {})

        dl.add_constraint(VersionConstraint(">=", "2"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint(">=", "2") ]})

        dl.add_constraint(VersionConstraint("<", "4"), "basic_fhs")
        self.assertEqual(dl.l, {"basic_fhs": [ VersionConstraint(">=", "2"), VersionConstraint("<", "4") ]})

        self.assertTrue(('basic_fhs', '2') in dl)
        self.assertTrue(('basic_fhs', '2.0') in dl)
        self.assertTrue(('basic_fhs', '2.1') in dl)
        self.assertTrue(('basic_fhs', '3.0') in dl)
        self.assertTrue(('basic_fhs', '3.9.9.9.9.9.9.9.9.9') in dl)
        self.assertFalse(('basic_fhs', '4') in dl)

if __name__ == '__main__':
    unittest.main()
