import networkx as nx

import os, shutil, json, sys
from argparse import ArgumentParser
from topo import CustomTopo, BASEDIR

import python_hosts
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import Host, OVSSwitch, RemoteController
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from multiprocessing import Process
from time import sleep
from segment_route import ETC_HOSTS_FILE
from tester import TestSuite


OUTPUT_PID_TABLE_FILE = "/tmp/pid_table_file.txt"

PRIVDIR = "/var/priv"


class BaseNode(Host):
    """
    Base class for nodes in the Mininet topology.

    Attributes:
        dir (str): The directory where the node stores its data.
        nets (list): A list of networks that the node is a part of.
    """
    def __init__(self, name, *args, **kwargs):
        """
        Initializes the node.

        Args:
            name (str): The name of the node.
            *args: Additional arguments.
            **kwargs: Additional keyword arguments.
        """
        dirs = [PRIVDIR]
        Host.__init__(self, name, privateDirs=dirs, *args, **kwargs)
        self.dir = f"/tmp/{name}"
        self.nets = []
        if not os.path.exists(self.dir):
            os.makedirs(self.dir)

    def config(self, **kwargs):
        """
        Configures the node by setting the IP address and starting any services
        defined in the start.sh script.

        Parameters:
            **kwargs: Additional configuration parameters for the node.

        Returns:
            None

        """
        Host.config(self, **kwargs)

        for intf in self.intfs.values():
            self.cmd(f"ifconfig {intf.name} down")
            self.cmd(f"ifconfig {intf.name} 0")
            self.cmd(f"ifconfig {intf.name} up")

        self.cmd(f"echo '{self.name}' > {PRIVDIR}/hostname")
        if os.path.isfile(f"{BASEDIR}{self.name}/start.sh"):
            print("Initializing")
            self.cmd(f"source {BASEDIR}{self.name}/start.sh")
        #if self.name == "r5" or self.name == "h14":
        #    self.cmd("sudo wireshark&")

    def cleanup(self):
        """
        Cleans up the node by removing any temporary files and stopping any
        services running on the node.

        Returns:
            None
        """
        def remove_if_exists(filename):
            if os.path.exists(filename):
                os.remove(filename)

        Host.cleanup(self)
        remove_if_exists(OUTPUT_PID_TABLE_FILE)


class Router(BaseNode):
    """
    A router node in the Mininet topology.
    """
    def __init__(self, name, *args, **kwargs):
        """
        Initializes the router node.

        Args:
            name (str): The name of the router node.
            *args: Additional arguments.
            **kwargs: Additional keyword arguments.
        """
        BaseNode.__init__(self, name, *args, **kwargs)

    def config(self, **kwargs):
        """
        Placeholder for additionally configuring the router node.
        """
        BaseNode.config(self, **kwargs)


def add_link(my_net, node1, node2):
    """
    Adds a link between two nodes in the Mininet topology.

    Args:
        my_net (Mininet): The Mininet instance.
        node1 (Host): The first node.
        node2 (Host): The second node.

    Returns:
        None
    """
    my_net.addLink(
        node1,
        node2,
        intfName1=f"{node1}-{node2}",
        intfName2=f"{node2}-{node1}",
    )


def create_topo(my_net, args):
    """
    Creates the Mininet topology based on the specified arguments.

    Args:
        my_net (Mininet): The Mininet instance.
        args (argparse.Namespace): The command line arguments.

    Returns:
        None
    """
    topo = CustomTopo(args.topo, args.size)
    topo.create_hosts()
    graph = topo.get_topo()

    for n in graph.nodes:
        if n[0] == "h":
            my_net.addHost(f"{n}", cls=BaseNode)
    for n in graph.nodes:
        if n[0] == "r":
            my_net.addHost(f"{n}", cls=Router)

    for n1, n2 in graph.edges:
        add_link(my_net, f"{n1}", f"{n2}")


def remove_nodes_from_etc_hosts(net):
    """
    Removes entries from /etc/hosts for all nodes in the Mininet instance.

    Args:
        net (Mininet): The Mininet instance.

    Returns:
        None
    """
    print("*** Removing entries from /etc/hosts\n")
    etc_hosts = python_hosts.hosts.Hosts()
    for host in net.hosts:
        etc_hosts.remove_all_matching(name=str(host))
    etc_hosts.write()


def stop_all():
    """
    Stops all processes running on the system.

    Args:
        None

    Returns:
        None

    """
    os.system("sudo mn -c")
    os.system("sudo killall sshd zebra isisd")


def extract_host_pid(dumpline: str) -> int:
    """
    Extracts the process ID from a Mininet host dump line.

    Args:
        dumpline (str): A Mininet host dump line.

    Returns:
        int: The process ID of the host.

    """
    temp = dumpline[dumpline.find("pid=") + 4 :]
    return int(temp[: len(temp) - 2])

def run_mn(args):
    """
    Runs mininet

    Args:
        args (argparse.Namespace): command line arguments

    Returns:
        None
    """
    # Initialize mininet
    net = Mininet(topo=None, build=False, controller=None, autoSetMacs=True, waitConnected=True)

    # Create topology
    create_topo(net, args)

    # Build and start mininet
    net.build()
    net.start()
    print("Dumping host connections")
    # Dump node connections
    dumpNodeConnections(net.hosts)

    # Open file to write host and pid pairs
    with open(OUTPUT_PID_TABLE_FILE, "w") as file:
        # Iterate over hosts and write host and pid pairs
        for host in net.hosts:
            file.write("%s %d\n" % (host, extract_host_pid(repr(host))))
    # Initialize test suite
    tester = TestSuite(net, operation_mode="Segment-Routing", args=args)

    # Stop mininet
    net.stop()
    # Stop sshd, zebra, and isisd processes
    stop_all()


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
    run_mn(args)


if __name__ == "__main__":
    main()
