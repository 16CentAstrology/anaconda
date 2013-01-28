
import unittest
import pyanaconda.storage.tsort

class TopologicalSortTestCase(unittest.TestCase):
    def runTest(self):
        items = [1, 2, 3, 4, 5]
        edges = [(5, 4), (4, 3), (3, 2), (2, 1)]
        graph = pyanaconda.storage.tsort.create_graph(items, edges)
        self._tsortTest(graph)

        edges = [(5, 4), (2, 3), (1, 5)]
        graph = pyanaconda.storage.tsort.create_graph(items, edges)
        self._tsortTest(graph)

        edges = [(5, 4), (4, 3), (3, 2), (2, 1), (3, 5)]
        graph = pyanaconda.storage.tsort.create_graph(items, edges)
        self.failUnlessRaises(pyanaconda.storage.tsort.CyclicGraphError,
                              pyanaconda.storage.tsort.tsort,
                              graph)

        edges = [(5, 4), (4, 3), (3, 2), (2, 1), (2, 3)]
        graph = pyanaconda.storage.tsort.create_graph(items, edges)
        self.failUnlessRaises(pyanaconda.storage.tsort.CyclicGraphError,
                              pyanaconda.storage.tsort.tsort,
                              graph)

        items = ['a', 'b', 'c', 'd']
        edges = [('a', 'c'), ('c', 'b')]
        graph = pyanaconda.storage.tsort.create_graph(items, edges)
        self._tsortTest(graph)

    def _tsortTest(self, graph):
        def check_order(order, graph):
            # since multiple solutions can potentially exist, just verify
            # that the ordering constraints are satisfied
            for parent, child in graph['edges']:
                if order.index(parent) > order.index(child):
                    return False
            return True

        try:
            order = pyanaconda.storage.tsort.tsort(graph)
        except Exception as e:
            self.fail(e)

        # verify output list is of the correct length
        self.failIf(len(order) != len(graph['items']),
                    "sorted list length is incorrect")

        # verify that all ordering constraints are satisfied
        self.failUnless(check_order(order, graph),
                        "ordering constraints not satisfied")


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(TopologicalSortTestCase)


if __name__ == "__main__":
    unittest.main()

