import matplotlib.pyplot as plt
import networkx as nx
import os, json, shutil
from python_hosts import Hosts
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import Host
from mininet.util import dumpNodeConnections
from subprocess import PIPE
from topo import CustomTopo, entry_finder
from time import sleep

ETC_HOSTS_FILE = "/etc/hosts"

USAGE_LIMIT = 70

SRLOGFILE = "srLog.txt"

class MetricCollector:
    """
    This class is used to collect metrics from the hosts in the network.

    Args:
        net (Mininet): The Mininet network object.

    Attributes:
        net (Mininet): The Mininet network object.
        metrics (dict): A dictionary that stores the metrics collected from the hosts. The keys are the host names and the values are dictionaries that contain the memory and CPU usage of the host.
    """
    def __init__(self, net, manager):
        """
        Initialize the MetricCollector class.
        """
        self.net = net
        self.pyhosts = Hosts()
        self.pyhosts.import_file(ETC_HOSTS_FILE)
        self.metrics = manager.dict() 
        self.metrics = {host.name: {} for host in self.net.hosts}

    def getBW(self, host):
        bws = {}
        for interface in host.intfs.values():
            if "lo" not in interface.name:
                intf = interface.name.split("-")
                intf = intf[1] if intf[0] in host.name else intf[0]
                host.cmd(f"iperf -c {entry_finder(name=intf, entries=self.pyhosts.entries)[0].address}")
                bw = host.popen(
                    ["iperf", "-c", f"{entry_finder(name=intf, entries=self.pyhosts.entries)[0].address}"],
                    stderr=PIPE,
                    stdout=PIPE,
                )
                sleep(1)
                try:
                    bws[intf] = float(json.loads(bw.communicate()[0]).stdout.read().splitlines()[-1].split("  ")[-1].split(" ")[0])
                except Exception as e:
                    raise SystemError(f"{e}\n{bw.communicate()}")
        return bws

    def collect_usage(self, host):
        """
        Collect the memory and CPU usage of a host.

        Args:
            host (Host): The host object.

        Returns:
            tuple: A tuple containing the memory and CPU usage of the host.
        """
        metrics = host.popen(
            ["python", "collect_usage.py"],
            stderr=PIPE,
            stdout=PIPE,
        )

        try:
            (mem_usage, cpu_usage) = json.loads(metrics.communicate()[0])
        except Exception as e:
            raise SystemError(f"{e}\n{metrics.communicate()}")

        return mem_usage, cpu_usage

    def collect_all_usage(self):
        """
        Collect the metrics from all the hosts in the network.
        """
        for host in self.net.hosts:
            (
                self.metrics[host.name]["memory_usage"],
                self.metrics[host.name]["cpu_usage"],
            ) = self.collect_usage(host)
            #self.metrics[host.name]['bandwidth_usage'] = self.getBW(host)


class SegmentRouter:
    """
    This class is used to route packets through a Segment Routing network.
    It uses the Dijkstra shortest path algorithm to find the best path between two hosts.
    It also updates the routing table on each host with the new Segment Routing entries.
    """
    def __init__(self, net, metrics_brain):
        """
        Initialize the SegmentRouter class.

        Args:
            net (Mininet): The Mininet network object.
        """
        self.net = net
        topo = CustomTopo(from_net=True)
        topo.create_from_net(net)
        self.G = topo.get_topo()
        self.pyhosts = Hosts()
        self.pyhosts.import_file(ETC_HOSTS_FILE)
        self.metrics_brain = metrics_brain

    def consolidate_edges(self):
        """
        This function is used to consolidate the edges of the network into a dictionary where the keys are the nodes and the values are a list of the adjacent nodes.

        Returns:
            dict: A dictionary where the keys are the nodes and the values are a list of the adjacent nodes.
        """
        edges = {node: [] for node in self.G.nodes}
        for edge in self.G.edges:
            edges[edge[0]].append(edge[1])
            edges[edge[1]].append(edge[0])
        return edges

    def find_weight(self):
        """
        This function is used to update the edge weights of the network based on the metrics collected from the hosts.
        The edge weights are used to determine the feasibility of using a specific edge for Segment Routing.
        If an edge is not feasible, the function assigns a weight of 0 to the edge, and assigns a higher weight to the edges that are feasible.
        """
        weighted_edges = {}
        edges = self.consolidate_edges()
        for edge in edges:
            endpoint_feasible = False
            death_scores = {endpoint: 0 for endpoint in edges[edge]}
            edge_scores = {}
            for endpoint in edges[edge]:
                rx_mem_score = (self.metrics_brain.metrics[endpoint]["memory_usage"] % USAGE_LIMIT)
                rx_cpu_score = (self.metrics_brain.metrics[endpoint]["cpu_usage"] % USAGE_LIMIT)
                # rx_bw_score = (self.metrics_brain.metrics[endpoint]["bandwidth_usage"][edge] % USAGE_LIMIT)
                tx_mem_score = (self.metrics_brain.metrics[endpoint]["memory_usage"] % USAGE_LIMIT)
                tx_cpu_score = (self.metrics_brain.metrics[endpoint]["cpu_usage"] % USAGE_LIMIT)
                # tx_bw_score = (self.metrics_brain.metrics[edge]["bandwidth_usage"][endpoint] % USAGE_LIMIT)

                if (self.metrics_brain.metrics[endpoint]["memory_usage"] / USAGE_LIMIT) >= 1:
                    death_scores[endpoint] = death_scores[endpoint] + (self.metrics_brain.metrics[endpoint]["memory_usage"] % USAGE_LIMIT)
                    rx_mem_score = 0

                if (self.metrics_brain.metrics[endpoint]["cpu_usage"] / USAGE_LIMIT) >= 1:
                    death_scores[endpoint] = death_scores[endpoint] + (self.metrics_brain.metrics[endpoint]["cpu_usage"] % USAGE_LIMIT)
                    rx_cpu_score = 0

                # if (self.metrics_brain.metrics[endpoint]["bandwidth_usage"][edge] / USAGE_LIMIT) >= 1:
                #    death_scores[endpoint] = death_scores[endpoint] + (self.metrics_brain.metrics[endpoint]["bandwidth_usage"][edge] % USAGE_LIMIT)
                #    rx_bw_score = 0

                if (self.metrics_brain.metrics[endpoint]["memory_usage"] / USAGE_LIMIT) >= 1:
                    death_scores[endpoint] = death_scores[endpoint] + (self.metrics_brain.metrics[endpoint]["memory_usage"] % USAGE_LIMIT)
                    tx_mem_score = 0

                if (self.metrics_brain.metrics[endpoint]["cpu_usage"] / USAGE_LIMIT) >= 1:
                    death_scores[endpoint] = death_scores[endpoint] + (self.metrics_brain.metrics[endpoint]["cpu_usage"] % USAGE_LIMIT)
                    tx_cpu_score = 0

                # if (self.metrics_brain.metrics[edge]["bandwidth_usage"][endpoint] / USAGE_LIMIT) >= 1:
                #    death_scores[endpoint] = death_scores[endpoint] + (self.metrics_brain.metrics[edge]["bandwidth_usage"][endpoint] % USAGE_LIMIT)
                #    tx_bw_score = 0

                edge_scores[endpoint] = 400 - (rx_mem_score + rx_cpu_score + tx_cpu_score + tx_mem_score) # + tx_bw_score + rx_bw_score
                if (rx_mem_score > 0 and rx_cpu_score > 0 and tx_mem_score > 0 and tx_cpu_score > 0):# and tx_bw_score > 0 and rx_bw_score > 0):
                    endpoint_feasible = True
            if endpoint_feasible:
                tmp_weights = {(edge, endpoint): {"weight": edge_scores[endpoint]+1} for endpoint in edges[edge]}
            else:
                smallest_gap = min(death_scores, key=death_scores.get)
                tmp_weights = {(edge, endpoint): {"weight": 400} for endpoint in edges[edge]}
                tmp_weights[(edge, smallest_gap)] = {"weight": edge_scores[endpoint]}

            weighted_edges.update(tmp_weights)
        nx.set_edge_attributes(self.G, weighted_edges)

    def route_node(self, start_node, end_node):
        """
        This function is used to find the shortest path between two nodes in the network.

        Parameters:
        start_node (str): The starting node of the path.
        end_node (str): The ending node of the path.

        Returns:
        List[str]: The list of nodes that make up the shortest path between the two nodes.
        """
        path = nx.shortest_path(
            self.G, start_node, end_node, weight="weight", method="dijkstra"
        )
        return path

    def check_weighted(self):
        """
            This function is used to check if the edge weights have been updated.
            If not, it updates the edge weights using the metrics collected from the hosts.
            """
        while not os.path.exists("tmp/metrics.json"):
            sleep(1)
        with open("tmp/metrics.json", "r") as f:
            self.metrics_brain.metrics = json.loads(f.read())
        self.find_weight()

    def route_all(self):
        """
        This function is used to route all the packets through the Segment Routing network.
        It uses the Dijkstra shortest path algorithm to find the best path between two hosts.
        It also updates the routing table on each host with the new Segment Routing entries.
        """
        print("Collecting Metrics...")
        self.metrics_brain.collect_all_usage()
        print("Collected")
        print(self.metrics_brain.metrics)
        self.find_weight()
        for host in self.net.hosts:
            for host2 in self.net.hosts:
                if host2!= host and "r" not in host.name and "r" not in host2.name:
                    path = self.route_node(host.name, host2.name)
                    encap = f"ip -6 route add {entry_finder(name=host2.name, entries=self.pyhosts.entries)[0].address[:-1]}/64 encap seg6 mode encap segs {','.join([entry_finder(name=item, entries=self.pyhosts.entries)[0].address for item in path[1:-1]])[:-1]}100 dev {path[1]}-{host.name}" #if len(path) > 2 else ""
                    # decap = f"ip -6 route add {entry_finder(name=path[0], entries=self.pyhosts.entries)[0].address[:-1]}100 encap seg6local action End.DT6 dev {path[-2]}-{path[-1]} table default"

                    with open(SRLOGFILE, "a") as f:
                        f.write(f"\nRouting from {host.name} to {host2.name} via {path}\n")
                        f.write(f"Segment Encap Command: {encap}\n")
                        # f.write(f"Segment Decap Command: {decap}\n")
                    print(host.intfs, file=open("srLog.txt", "a"))
                    self.net.getNodeByName(path[1]).cmd("ip route flush table default")
                    self.net.getNodeByName(path[1]).cmd(encap)
                    # self.net.getNodeByName(path[-2]).cmd("ip route flush table default")
                    # self.net.getNodeByName(path[-2]).cmd(decap)

    def get_sids(self, path):
        sids = []
        for index in range(len(path[1:])):
            if "r" in path[index+1] and "r" in path[index]:
                if int(path[index+1][1:]) > int(path[index][1:]):
                    addyr = f"{path[index][1:]}:{path[index+1][1:]}::2"
                else:
                    addyr = f"{path[index+1][1:]}:{path[index][1:]}::1"
                sids.append(f"fcf0:0:{addyr}")
            else:
                sids.append(entry_finder(name=path[index+1], entries=self.pyhosts.entries)[0].address)
                
        return sids

    def route_route(self, host1, host2):
        """
        This function is used to route a specific packet from host1 to host2 through the Segment Routing network.
        It uses the Dijkstra shortest path algorithm to find the best path between two hosts.
        It also updates the routing table on each host with the new Segment Routing entries.

        Parameters:
        host1 (Host): The source host of the packet.
        host2 (Host): The destination host of the packet.

        Returns:
        None
        """
        self.check_weighted()
        def single_route(host1, host2, initial_route=False):
            path = self.route_node(host1.name, host2.name)
            encap = f"ip -6 route add {entry_finder(name=host2.name, entries=self.pyhosts.entries)[0].address[:-1]}/64 encap seg6 mode encap segs {','.join(self.get_sids(path[:-1]))} dev {path[1]}-{host1.name}" if len(path) > 2 else ""
            # decap = f"ip -6 route add {entry_finder(name=path[0], entries=self.pyhosts.entries)[0].address[:-1]}100 encap seg6local action End.DT6 dev {path[-2]}-{path[-1]} table default"
            with open(SRLOGFILE, "a") as f:
                f.write(f"\nRouting from {host1.name} to {host2.name} via {path[1:]}\n")
                f.write(f"Segment Encap Command: {encap}\n")
                # f.write(f"Segment Decap Command: {decap}\n")
            print(host1.intfs, file=open("srLog.txt", "a"))
            if initial_route:
                self.net.getNodeByName(path[1]).cmd("ip -6 route flush table default")
                self.net.getNodeByName(path[-2]).cmd("ip -6 route flush table default")
            self.net.getNodeByName(path[1]).cmd(encap)
            # self.net.getNodeByName(path[-2]).cmd(decap)

        single_route(host1, host2, initial_route=True)
        single_route(host2, host1)
