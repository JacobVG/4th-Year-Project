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

ETC_HOSTS_FILE = "/etc/hosts"

USAGE_LIMIT = 70

SRLOGFILE = "srLog.txt"

class MetricCollector:
    def __init__(self, net):
        self.net = net
        self.metrics = {host.name: {} for host in self.net.hosts}

    def collect_usage(self, host):
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
        for host in self.net.hosts:
            (
                self.metrics[host.name]["memory_usage"],
                self.metrics[host.name]["cpu_usage"],
            ) = self.collect_usage(host)


class SegmentRouter:
    def __init__(self, net):
        self.net = net
        topo = CustomTopo(from_net=True)
        topo.create_from_net(net)
        self.G = topo.get_topo()
        self.pyhosts = Hosts()
        self.pyhosts.import_file(ETC_HOSTS_FILE)
        self.metrics_brain = MetricCollector(net)

    def consolidate_edges(self):
        edges = {node: [] for node in self.G.nodes}
        for edge in self.G.edges:
            edges[edge[0]].append(edge[1])
            edges[edge[1]].append(edge[0])
        return edges

    def find_weight(self):
        weighted_edges = {}
        edges = self.consolidate_edges()
        for edge in edges:
            endpoint_feasible = False
            death_scores = {endpoint: 0 for endpoint in edges[edge]}
            edge_scores = {}
            for endpoint in edges[edge]:
                rx_mem_score = (self.metrics_brain.metrics[endpoint]["memory_usage"] % USAGE_LIMIT)
                rx_cpu_score = (self.metrics_brain.metrics[endpoint]["cpu_usage"] % USAGE_LIMIT)
                tx_mem_score = (self.metrics_brain.metrics[endpoint]["memory_usage"] % USAGE_LIMIT)
                tx_cpu_score = (self.metrics_brain.metrics[endpoint]["cpu_usage"] % USAGE_LIMIT)

                if (self.metrics_brain.metrics[endpoint]["memory_usage"] / USAGE_LIMIT) >= 1:
                    death_scores[endpoint] = death_scores[endpoint] + (self.metrics_brain.metrics[endpoint]["memory_usage"] % USAGE_LIMIT)
                    rx_mem_score = 0

                if (self.metrics_brain.metrics[endpoint]["cpu_usage"] / USAGE_LIMIT) >= 1:
                    death_scores[endpoint] = death_scores[endpoint] + (self.metrics_brain.metrics[endpoint]["cpu_usage"] % USAGE_LIMIT)
                    rx_cpu_score = 0

                if (self.metrics_brain.metrics[endpoint]["memory_usage"] / USAGE_LIMIT) >= 1:
                    death_scores[endpoint] = death_scores[endpoint] + (self.metrics_brain.metrics[endpoint]["memory_usage"] % USAGE_LIMIT)
                    tx_mem_score = 0

                if (self.metrics_brain.metrics[endpoint]["cpu_usage"] / USAGE_LIMIT) >= 1:
                    death_scores[endpoint] = death_scores[endpoint] + (self.metrics_brain.metrics[endpoint]["cpu_usage"] % USAGE_LIMIT)
                    tx_cpu_score = 0

                edge_scores[endpoint] = rx_mem_score + rx_cpu_score + tx_cpu_score + tx_mem_score
                if (rx_mem_score > 0 and rx_cpu_score > 0 and tx_mem_score > 0 and tx_cpu_score > 0 ):
                    endpoint_feasible = True
            if endpoint_feasible:
                tmp_weights = {(edge, endpoint): {"weight": edge_scores[endpoint]+1} for endpoint in edges[edge]}
            else:
                smallest_gap = min(death_scores, key=death_scores.get)
                tmp_weights = {(edge, endpoint): {"weight": 0} for endpoint in edges[edge]}
                tmp_weights[(edge, smallest_gap)] = {"weight": edge_scores[endpoint]}

            weighted_edges.update(tmp_weights)
        nx.set_edge_attributes(self.G, weighted_edges)

    def route_node(self, start_node, end_node):
        path = nx.shortest_path(
            self.G, start_node, end_node, weight="weight", method="dijkstra"
        )
        return path

    def route_all(self):
        """
        This function is used to route all the packets through the Segment Routing network.
        It uses the shortest path algorithm to find the best path between two hosts.
        It also updates the routing table on each host with the new Segment Routing entries.
        """
        print("Collecting Metrics...")
        self.metrics_brain.collect_all_usage()
        print("Collected")
        print(self.metrics_brain.metrics)
        self.find_weight()
        for host in self.net.hosts:
            for host2 in self.net.hosts:
                if host2!= host:
                    path = self.route_node(host.name, host2.name)[1:]
                    encap = f"ip -6 route add {entry_finder(name=host2.name, entries=self.pyhosts.entries)[0].address[:-1]}/64 encap seg6 mode encap segs {','.join([entry_finder(name=item, entries=self.pyhosts.entries)[0].address for item in path[:-1]])[:-1]}100 dev {host.name}-{path[0]}" if len(path) > 1 else ""
                    decap = f"ip -6 route add {entry_finder(name=path[0], entries=self.pyhosts.entries)[0].address[:-1]}100 encap seg6local action End.DT6 table 254 dev {host.name}-{path[0]}"
                    with open(SRLOGFILE, "a") as f:
                        f.write(f"\nRouting from {host.name} to {host2.name} via {path}\n")
                        f.write(f"Segment Encap Command: {encap}\n")
                        f.write(f"Segment Decap Command: {decap}\n")
                    print(host.intfs, file=open("srLog.txt", "a"))
                    host.cmd(encap)
                    host2.cmd(decap)
