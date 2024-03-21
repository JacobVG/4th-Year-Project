from argparse import ArgumentParser
import pdb
from mininet.cli import CLI
from mininet.topo import Topo
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import Host, OVSSwitch, RemoteController
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from topo import CustomTopo
from tester import TestSuite

class NoRoutingTopo(Topo):
    def __init__(self):
        Topo.__init__(self)
        topo = CustomTopo(dump=False, read_dump=True)
        topo.create_hosts()
        graph = topo.get_topo()
        curr_nodes = {}
        for n in graph.nodes:
            if n[0] == "h":
                curr_nodes[f"{n}"] = self.addHost(f"{n}")
        for n in graph.nodes:
            if n[0] == "r":
                curr_nodes[f"{n}"] = self.addSwitch(f"{n}")
        for n1, n2 in graph.edges:
            self.addLink(curr_nodes[f"{n1}"], curr_nodes[f"{n2}"])


def run_mn_noSR(args):
    c = RemoteController("controller", port=6653)
    net = Mininet(topo=NoRoutingTopo(), build=True, controller=RemoteController, autoSetMacs=True, switch=OVSSwitch)
    net.addController(c)
    net.start()
    tester = TestSuite(net, operation_mode="Non-Segment-Routing", args=args)
    net.stop()


def parse_arguments():
    """
    Parses command line arguments for the Mininet topology.

    Returns:
        ArgumentParser: The ArgumentParser object with the parsed arguments.
    """
    parser = ArgumentParser(
        description="Emulation of a Mininet topology for Segment Routing"
    )
    parser.add_argument(
        "-t",
        "--topo",
        default="linear",
        action="store",
        type=str,
        help="This is the argument for the type of topology you wish to create the current options are [linear, star, tree]",
    )
    parser.add_argument(
        "-s",
        "--size",
        default=3,
        action="store",
        type=int,
        help="This is the argument to determine the size of your topology.",
    )
    parser.add_argument(
        "--debug-mode",
        default=False,
        action="store_true",
        help="Enable debug mode for logging purposes",
    )

    args = parser.parse_args()
    return args


def main():
    args = parse_arguments()
    setLogLevel("debug") if args.debug_mode else setLogLevel("info")
    run_mn_noSR(args)


if __name__ == "__main__":
    main()
