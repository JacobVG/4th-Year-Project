import networkx as nx

import os, shutil, json
from argparse import ArgumentParser
from topo import CustomTopo, BASEDIR

import python_hosts
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import Host
from mininet.util import dumpNodeConnections
from multiprocessing import Process
from time import sleep
from segment_route import MetricCollector, SegmentRouter, ETC_HOSTS_FILE
from tester import TestSuite


OUTPUT_PID_TABLE_FILE = "/tmp/pid_table_file.txt"

PRIVDIR = "/var/priv"

ADD_ETC_HOSTS = True


class BaseNode(Host):
    def __init__(self, name, *args, **kwargs):
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
            self.cmd(f"ifconfig {intf.name} 0")

        self.cmd(f"echo '{self.name}' > {PRIVDIR}/hostname")
        if os.path.isfile(f"{BASEDIR}{self.name}/start.sh"):
            print("Initializing")
            print(self.cmd(f"source {BASEDIR}{self.name}/start.sh"))
        if self.name == "r5" or self.name == "h14":
            self.cmd("sudo wireshark&")

    def cleanup(self):
        def remove_if_exists(filename):
            if os.path.exists(filename):
                os.remove(filename)

        Host.cleanup(self)
        # Rm dir
        if os.path.exists(self.dir):
            shutil.rmtree(self.dir)

        remove_if_exists(f"{BASEDIR}{self.name}/zebra.pid")
        remove_if_exists(f"{BASEDIR}{self.name}/zebra.log")
        remove_if_exists(f"{BASEDIR}{self.name}/zebra.sock")
        remove_if_exists(f"{BASEDIR}{self.name}/isis8d.pid")
        remove_if_exists(f"{BASEDIR}{self.name}/isis8d.log")
        remove_if_exists(f"{BASEDIR}{self.name}/isisd.log")
        remove_if_exists(f"{BASEDIR}{self.name}/isisd.pid")

        remove_if_exists(OUTPUT_PID_TABLE_FILE)


class Router(BaseNode):
    def __init__(self, name, *args, **kwargs):
        BaseNode.__init__(self, name, *args, **kwargs)


def add_link(my_net, node1, node2):
    my_net.addLink(
        node1,
        node2,
        intfName1=f"{node1}-{node2}",
        intfName2=f"{node2}-{node1}",
    )


def create_topo(my_net, args):
    topo = CustomTopo(args.topo, args.size)
    topo.create_hosts()
    graph = topo.get_topo()

    for n in graph.nodes:
        if n[0] == "r":
            my_net.addHost(f"{n}", cls=Router)
        elif n[0] == "h":
            my_net.addHost(f"{n}", cls=BaseNode)
    for n1, n2 in graph.edges:
        add_link(my_net, f"{n1}", f"{n2}")


def add_nodes_to_etc_hosts():
    etc_hosts = python_hosts.hosts.Hosts()
    count = etc_hosts.import_file(ETC_HOSTS_FILE)
    count = count["add_result"]["ipv6_count"] + count["add_result"]["ipv4_count"]
    print(f"*** Added {count} entries to /etc/hosts\n")


def remove_nodes_from_etc_hosts(net):
    print("*** Removing entries from /etc/hosts\n")
    etc_hosts = python_hosts.hosts.Hosts()
    for host in net.hosts:
        etc_hosts.remove_all_matching(name=str(host))
    etc_hosts.write()


def stop_all():
    os.system("sudo mn -c")
    os.system("sudo killall sshd zebra isisd")


def extract_host_pid(dumpline):
    temp = dumpline[dumpline.find("pid=") + 4 :]
    return int(temp[: len(temp) - 2])


def check_metrics(net):
    router = SegmentRouter(net)
    while True:
        router.route_all()
        sleep(60)


def run_tester(net):
    sleep(60)
    tester = TestSuite(net)
    while True:
        tester.code_brain()
        #tester.custom_pinger() 


def run_mn(args):
    "Runs mininet"
    net = Mininet(topo=None, build=False, controller=None, autoSetMacs=False)
    create_topo(net, args)

    net.build()
    net.start()
    print("Dumping host connections")
    dumpNodeConnections(net.hosts)

    with open(OUTPUT_PID_TABLE_FILE, "w") as file:
        for host in net.hosts:
            file.write("%s %d\n" % (host, extract_host_pid(repr(host))))

    if ADD_ETC_HOSTS:
        add_nodes_to_etc_hosts()

    metric_checker = Process(target=check_metrics, args=(net,))
    cli_runner = Process(target=run_tester, args=(net,))
    metric_checker.start()
    cli_runner.start()
    metric_checker.join()
    cli_runner.join()

    if ADD_ETC_HOSTS:
        remove_nodes_from_etc_hosts(net)

    net.stop()
    stop_all()


def parse_arguments():
    parser = ArgumentParser(
        description="Emulation of a Mininet topology (8 routers running "
        "IS-IS, 1 controller out-of-band"
    )
    parser.add_argument(
        "--no-etc-hosts",
        dest="add_etc_hosts",
        action="store_false",
        default=True,
        help="Define whether to add Mininet nodes to /etc/hosts file or not",
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

    args = parser.parse_args()
    return args


def __main():
    global ADD_ETC_HOSTS
    args = parse_arguments()
    ADD_ETC_HOSTS = args.add_etc_hosts
    setLogLevel("info")
    run_mn(args)


if __name__ == "__main__":
    __main()
