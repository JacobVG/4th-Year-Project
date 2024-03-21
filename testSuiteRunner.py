from argparse import Namespace
from main import run_mn
from non_seg_route import run_mn_noSR

def run_testSuite():
    test_cases = {"tree": 4, "linear": 20, "mesh": 20}
    for topo in test_cases.keys():
        for size in range(1, test_cases[topo]):
            args = Namespace(debug_mode=False, size=size, topo=topo)
            run_mn(args)
            run_mn_noSR(args)

if __name__ == "__main__":
    run_testSuite()