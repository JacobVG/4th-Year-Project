from copy import copy
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3, ether
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.topology import event
from ryu.topology.api import get_all_switch, get_all_link
from ryu.lib import dpid as dpid_lib
from ryu.controller import dpset
import networkx as nx
import asyncio


class SuperSickSynapse(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SuperSickSynapse, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.working_topology = TopoStructure()

    def get_topology_data(self):
        print("Collecting Switches")
        # self.working_topology.topo_raw_switches = copy(get_all_switch(self))
        print("Collecting Links")
        self.working_topology.topo_raw_links = copy(get_all_link(self))
        print("Collected")
        print(f"{self.working_topology.print_links()}\n{self.working_topology.print_switches()}")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def handler_switch_enter(self, ev):
        msg = ev.msg
        print(msg)
        self.get_topology_data()


class TopoStructure():
    def __init__(self, *args, **kwargs):
        self.topo_raw_switches = []
        self.topo_raw_links = []
        self.topo_links = []

        self.net = nx.DiGraph()

    def print_links(self, func_str=None):
        print(" \t"+str(func_str)+": Current Links:")
        for l in self.topo_raw_links:
            print (" \t\t"+str(l))

    def print_switches(self, func_str=None):
        print(" \t"+str(func_str)+": Current Switches:")
        for s in self.topo_raw_switches:
            print (" \t\t"+str(s))


def main():
    ryu_app = SuperSickSynapse()
    ryu_app_manager = app_manager.AppManager()
    ryu_app_manager.run()
    ryu_app.start()


if __name__ == "__main__":
    main()
