import matplotlib.pyplot as plt
import networkx as nx
import argparse, os, shutil, pickle
from python_hosts import Hosts, HostsEntry

BASEDIR = f"{os.getcwd()}/nodeconf/"
TEMPLATES_DIR = f"{os.getcwd()}/nodeconf_templates/"

def entry_finder(name, entries):
    results = []
    for entry in entries:
        if entry.entry_type not in ("ipv4", "ipv6"):
            continue
        if name not in entry.names:
            continue
        results.append(entry)

    return results

class CustomTopo:
    def __init__(
        self,
        topo_name="linear",
        size=3,
        plot_figure=False,
        start_node=None,
        end_node=None,
        from_net=False,
        dump=True,
        read_dump=False,
    ):
        self.path_edges = []
        if not from_net and not read_dump:
            print("Creating topologies...")
            self.topo = topo_name
            self.size = size
            self.create_topologies()
            if dump:
                self.dump_topologies()
        if read_dump:
            self.read_topologies()
        if start_node and end_node:
            self.route_nodes(start_node, end_node)
        if plot_figure:
            self.plot_topologies()

    def get_topo(self):
        return self.G

    def dump_topologies(self):
        pickle.dump(self.G, open(f"working_topology.pickle", "wb"))

    def read_topologies(self):
        self.G = pickle.load(open(f"working_topology.pickle", "rb"))

    def create_from_net(self, net):
        self.G = nx.Graph()
        [self.G.add_node(host.name) for host in net.hosts]
        for link in net.links:
            self.G.add_edge(link.intf1.node.name, link.intf2.node.name)

    def create_linear(self):
        self.G = nx.Graph()
        for node_num in range(1, self.size+1):
            self.G.add_node(f"r{node_num}")
            self.G.add_node(f"h{node_num}")
            self.G.add_edge(f"r{node_num}", f"h{node_num}")
        self.G.add_edges_from(
            [(f"r{node_num}", f"r{node_num+1}") for node_num in range(1, self.size)]
        )

    def create_tree(self):
        self.G = nx.balanced_tree(self.size, self.size)
        self.rename_nodes()

    def create_star(self):
        self.G = nx.star_graph(self.size)
        self.rename_nodes()

    def create_mesh(self):
        self.G = nx.Graph()
        for i in range(self.size):
            self.G.add_node(f"r{i}0")
            for j in range(1, self.size):
                self.G.add_node(f"h{i}{j}")
        for i in range(self.size):
            node_id = f"r{i}0"
            neighbour_id = f"r{i+1}0"
            self.G.add_edge(node_id, neighbour_id)
            for j in range(self.size):
                node_id = f"h{i}{j+1}"
                if i < self.size:
                    neighbor_id = f"h{i+1}{j+1}"
                    self.G.add_edge(node_id, neighbor_id)
                neighbor_id = f"r{i}0"
                self.G.add_edge(node_id, neighbor_id)
        for i in range(self.size):
            self.G.add_edge(f"r{self.size}0", f"h{self.size}{i+1}")
        
    def create_web(self):
        def child_finder(parent, layer, layers, edge_dict):
            for child in edge_dict[parent]:
                layers[f"l{layer}"].append(child)
                if edge_dict.get(child, None):
                    layers = child_finder(child, layer + 1, layers, edge_dict)
            return layers

        self.G = nx.balanced_tree(self.size, self.size)
        edge_dict = {i: [] for i in self.G.nodes}
        for edge in self.G.edges:
            edge_dict[edge[0]].append(edge[1])

        edge_dict = {key: value for key, value in edge_dict.items() if len(value) > 1}

        layers = {f"l{i}": [] for i in range(1, self.size + 1)}
        layers = child_finder(list(edge_dict.keys())[0], 1, layers, edge_dict)

        for layer in layers:
            for index in range(len(layers[layer])-1):
                if index == 0:
                    self.G.add_edge(layers[layer][index], layers[layer][-1])
                self.G.add_edge(layers[layer][index], layers[layer][index + 1])
        hosts = layers[list(layers.keys())[-1]]
        self.rename_nodes(hosts)

    def create_topologies(self):
        self.topologies_dict = {
            "linear": "create_linear",
            "tree": "create_tree",
            "star": "create_star",
            "mesh": "create_mesh",
            "web": "create_web",
        }
        exec(f"self.{self.topologies_dict[self.topo]}()")

    def configure_hosts(self, hosts):
        with open(os.path.join(TEMPLATES_DIR, "node/start-template.sh"), "r") as template:
            node_start_lines = template.readlines()
        with open(os.path.join(TEMPLATES_DIR, "router/start-template.sh"), "r") as template:
            router_start_lines = template.readlines()

        for node in self.G.nodes():
            node_path = os.path.join(BASEDIR, node)
            try:
                shutil.rmtree(node_path)
            except OSError as e:
                pass
            os.makedirs(node_path, exist_ok=True)
            curr_entry = entry_finder(name=node, entries=hosts.entries)[0]
            if "h" in node:
                all_connections = list(self.G.edges(node))[0]
                connected_name = all_connections[0] if all_connections[1] == node else all_connections[1]
                with open(f"{node_path}/start.sh", "w+") as starter:
                    starter.write("#/bin/sh\n\n")
                    starter.write(f"NODE_NAME={node}\n")
                    starter.write(f"GW_NAME={connected_name}\n")
                    starter.write(f"IF_NAME={node}-{connected_name}\n")
                    starter.write(f"IP_ADDR={curr_entry.address}/64\n")
                    starter.write(f"GW_ADDR={curr_entry.address[:-1]}1\n\n")
                    for line in node_start_lines:
                        starter.write(line)
            elif "r" in node:
                with open(f"{node_path}/isisd.conf", "w+") as isisd:
                    isisd.write(f"hostname {node}\n")
                    isisd.write("password zebra\n")
                    isisd.write(f"log file {node_path}/isisd.log\n")
                    isisd.write("!\n")
                    isisd.write("!\n")
                    isisd.write("interface eth0\n")
                    isisd.write(" ipv6 router isis 1\n")
                    isisd.write(" ip router isis 1\n")
                    isisd.write(" isis hello-interval 5\n")
                    counter = 1
                    for edge in self.G.edges(node):
                        counter = counter + 1
                        ifconnect = edge[0] if edge[1] == node else edge[1]

                        isisd.write("!\n")
                        isisd.write(f"interface {node}-{ifconnect}\n")
                        isisd.write(f" ipv6 router isis {counter}\n")
                        isisd.write(f" ip router isis {counter}\n")
                        isisd.write(" isis hello-interval 5\n")
                    counter = counter + 1
                    isisd.write("!\n")
                    isisd.write("interface lo\n")
                    isisd.write(f" ipv6 router isis {counter}\n")
                    isisd.write(f" ip router isis {counter}\n")
                    isisd.write(" isis hello-interval 5\n")
                    isisd.write("!\n")
                    isisd.write(f"router isis FOO\n")
                    isisd.write(f" net 49.0001.1111.1111.{node[1:].zfill(4)}.00\n")
                    isisd.write(" is-type level-2-only\n")
                    isisd.write(" metric-style wide\n")
                    isisd.write("!\n")
                    isisd.write("line vty\n")

                with open(f"{node_path}/zebra.conf", "w+") as zebra:
                    zebra.write("! -*- zebra -*-\n\n")
                    zebra.write("!\n")
                    zebra.write(f"hostname {node}\n")
                    zebra.write(f"log file {node_path}/zebra.log\n")
                    zebra.write("!\n")
                    zebra.write("debug zebra events\n")
                    zebra.write("debug zebra rib\n")
                    for edge in self.G.edges(node):
                        ifconnect = edge[0] if edge[1] == node else edge[1]
                        zebra.write("!\n")
                        zebra.write(f"interface {node}-{ifconnect}\n")
                        if "r" in ifconnect and "r" in node:
                            if int(node[1:]) > int(ifconnect[1:]):
                                addyr = f"{ifconnect[1:]}:{node[1:]}::2"
                            else:
                                addyr = f"{node[1:]}:{ifconnect[1:]}::1"
                            zebra.write(f" ipv6 address fcf0:0:{addyr}/64\n")
                        else:
                            zebra.write(f" ipv6 address {entry_finder(name=ifconnect, entries=hosts.entries)[0].address[:-1]}1/64\n")
                    zebra.write("!\n")
                    zebra.write("interface lo\n")
                    zebra.write(f" ipv6 address {curr_entry.address}/32\n")
                    zebra.write("!\n")
                    zebra.write("ipv6 forwarding\n")
                    zebra.write("!\n")
                    zebra.write("line vty")

                with open(f"{node_path}/start.sh", "w+") as starter:
                    starter.write("#!/bin/sh\n\n")
                    starter.write(f"BASE_DIR={BASEDIR}\n")
                    starter.write(f"NODE_NAME={node}\n")
                    for line in router_start_lines:
                        starter.write(line)

    def create_hosts(self):
        curr_hosts = Hosts()
        curr_hosts.import_file("/etc/hosts")
        [curr_hosts.remove_all_matching(name=host) for host in self.G.nodes()]
        new_hosts = [
            HostsEntry(entry_type="ipv4", address="127.0.0.1", names=["localhost"]),
            HostsEntry(entry_type="ipv4", address="127.0.1.1", names=["rose-srv6"]),
            HostsEntry(entry_type="ipv6", address="::1", names=["ip6-localhost", "ip6-loopback"]),
            HostsEntry(entry_type="ipv6", address="fe00::0", names=["ip6-localnet"]),
            HostsEntry(entry_type="ipv6", address="ff00::0", names=["ip6-mcastprefix"]),
            HostsEntry(entry_type="ipv6", address="ff02::1", names=["ip6-allnodes"]),
            HostsEntry(entry_type="ipv6", address="ff02::2", names=["ip6-allrouters"]),
        ]
        new_hosts.extend(
            [
                (
                    HostsEntry(
                        entry_type="ipv6",
                        address=f"fd00:0:{node[1:]}::2",
                        names=[f"{node}"],
                    )
                    if "h" in node
                    else HostsEntry(
                        entry_type="ipv6",
                        address=f"fcff:{node[1:]}::1",
                        names=[f"{node}"],
                    )
                )
                for node in self.G.nodes()
            ]
        )
        curr_hosts.add(entries=new_hosts)
        curr_hosts.write()
        print(f"*** Added {len(new_hosts)} new hosts to /etc/hosts\n")
        self.configure_hosts(curr_hosts)

    def rename_nodes(self, hosts=None):
        if not hosts:
            new_labels = {
                node: f"r{node+1}" if len(self.G.edges(node)) > 1 else f"h{node+1}"
                for node in self.G.nodes()
            }
        else:
            new_labels = {
                node: f"r{node+1}" if not node in hosts else f"h{node+1}"
                for node in self.G.nodes()
            }
        nx.relabel_nodes(self.G, mapping=new_labels, copy=False)

    def route_nodes(self, start_node, end_node):
        path = nx.shortest_path(self.G, start_node, end_node)
        print(path)
        self.path_edges = list(zip(path, path[1:]))

    def plot_topologies(self):
        edge_colours = [
            (
                "red"
                if edge in self.path_edges or tuple(reversed(edge)) in self.path_edges
                else "black"
            )
            for edge in self.G.edges()
        ]
        pos = nx.nx_agraph.graphviz_layout(self.G, prog="twopi")
        nx.draw_networkx_nodes(self.G, pos, node_size=750)
        nx.draw_networkx_edges(self.G, pos, edge_color=edge_colours)
        nx.draw_networkx_labels(self.G, pos, font_color="white")
        plt.gca().set_facecolor("none")

        plt.savefig("topo.png")


def create_parser():
    parser = argparse.ArgumentParser(
        prog="Topology Creator",
        description="This creates a topology using the networkx library and returns it as a value importable to Mininet",
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
        "-p",
        "--plot",
        default=False,
        action="store_true",
        help="This is the argument to plot the network you are creating to a file called topo.png.",
    )
    parser.add_argument(
        "--start",
        default=None,
        action="store",
        type=str,
        help="This is the argument for the starting node for path calculation in testing.",
    )
    parser.add_argument(
        "--end",
        default=None,
        action="store",
        type=str,
        help="This is the argument for the ending node for path calculation in testing",
    )

    args = parser.parse_args()
    return args


def main():
    args = create_parser()
    CustomTopo(
        topo_name=args.topo,
        size=args.size,
        plot_figure=args.plot,
        start_node=args.start,
        end_node=args.end,
    )
    print("Done")


if __name__ == "__main__":
    main()
