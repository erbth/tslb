"""
Balance the forest of rootfs images.
"""
from concurrent import futures
from tslb import rootfs
from tslb import tclm
import math
import sys

available_balancers = []


class Balancer:
    """
    An abstract base class from which forest balancer implementations must
    inherit.
    """
    def compute_operations(self):
        """
        Compute operations to apply to the forest. An operation is a tuple
        (image id:int, operation type:str). Currently only 'flatten' is a valid
        operation type.

        :returns: A sequence of operations.
        :rtype:   Sequence(Tuple(int, str))
        """
        raise NotImplementedError

    def set_out(self, out):
        """
        Set logging output stream.

        :param out: sys.stdout-like object
        """
        raise NotImplementedError


class SimpleBalancer(Balancer):
    """
    Simple balancer to limit fanout and height.

    fanout:     number of children per image
    height (h): number of edges from the root of a tree to the most-distant
                node, e.g. 2 in the following example:

                               0 - 1
                                \- 2 - 3
    """
    def __init__(self, fanout_max, h_max):
        self._fanout_max = fanout_max
        self._h_max = h_max
        self._out = sys.stdout

    def compute_operations(self):
        ops = []

        # Build a representation of the rootfs forest R as adjacency list.
        print("  Building forest graph R...", file=self._out)
        R = {}

        # Lock the entire rootfs image hierarchy while accessing images s.t.
        # the forest does not change
        forest_lock = tclm.define_lock('tslb.rootfs')
        with tclm.lock_S(forest_lock):
            print("  Forest locked.", file=self._out)
            for img in rootfs.list_images():
                R[img] = set(rootfs.Image(img).list_children())
            print("  Forest unlocked.", file=self._out)

        # Backwards edges (transposed graph)
        Rt = {v: None for v in R}
        for v, cs in R.items():
            for c in cs:
                Rt[c] = v

        # Operations on the simulated graph
        def flatten(imgid):
            if Rt[imgid] is not None:
                R[Rt[imgid]].remove(imgid)

                Rt[imgid] = None
                ops.append((imgid, 'flatten'))

        # (1.) limit fanout
        print("\n  Limiting fanout to %d ..." % self._fanout_max, file=self._out)
        for v in list(R.keys()):
            cs = R[v]
            if len(cs) > self._fanout_max:
                print("    fanout(%d) = %d" % (v, len(cs)), file=self._out)
                for c in list(cs):
                    flatten(c)

        # (2.) limit height
        print("\n  Limiting height to %d ..." % self._h_max, file=self._out)

        def h(v):
            """
            Height of a node in 'its' tree.
            """
            if Rt[v] is None:
                return 0
            else:
                return 1 + h(Rt[v])

        def h_tree(r):
            """
            Compute height of tree rooted at r.
            """
            if not R[r]:
                return 0
            else:
                return 1 + max(h_tree(w) for w in R[r])

        h_forest = max(h(v) for v in R)
        print("    height of forest: %d" % h_forest, file=self._out)

        while True:
            # \exists tree t with h(t) > h_max
            t = None
            for v in R:
                if Rt[v] is not None:
                    continue

                ht = h_tree(v)
                if ht > self._h_max:
                    t = v
                    break

            if t is None:
                break

            print("    h_tree(%d) = %d" % (t, ht), file=self._out)

            # Flatten all images of the tree with h(v) == ceil(ht / 2)
            hf = math.ceil(ht / 2)
            to_flatten = []

            def visit(v):
                if h(v) == hf:
                    print("      flatten(%d) with h = %d" % (v, hf), file=self._out)
                    to_flatten.append(v)

                for w in R[v]:
                    visit(w)

            visit(t)
            for v in to_flatten:
                flatten(v)

        print()
        return ops

    def set_out(self, out):
        self._out = out

available_balancers.append(SimpleBalancer)


def balance_forest(balancer, concurrent_flatten=5, out=sys.stdout):
    """
    Balance the forest of rootfs images with the given balancer. Use like
    `balance_forest(balancer=SimpleBalancer(...))`.

    :param Balancer balancer:
    :param int concurrent_flatten: How many concurrent flatten operations to
        issue.
    :param out: sys.stdout-like object for logging
    """
    print("Computing operations...", file=out)
    balancer.set_out(out)
    ops = balancer.compute_operations()

    print("Balancing forest...", file=out)
    with futures.ThreadPoolExecutor(concurrent_flatten) as exe:
        def work(op):
            imgid, optype = op
            if optype == 'flatten':
                try:
                    img = rootfs.Image(imgid)
                    print("  flatten %d" % imgid)
                    img.flatten()

                except rootfs.NoSuchImage:
                    pass

            else:
                raise RuntimeError("Invalid operation type '%s'." % optype)

        fs = [exe.submit(work, op) for op in ops]

        # Wait for futures and retrieve results to let exceptions occur
        res = futures.wait(fs, return_when=futures.ALL_COMPLETED)
        for f in res.done:
            f.result()

    print("\nfinished.", file=out)
