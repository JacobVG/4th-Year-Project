from segment_route import entry_finder, ETC_HOSTS_FILE
from python_hosts import Hosts
from time import sleep

class TestSuite:
    def __init__(self, net):
        self.net = net
        self.pyhosts = Hosts()
        self.pyhosts.import_file(ETC_HOSTS_FILE)

    def ping_all(self):
        self.net.pingAll()

    def custom_pinger(self):
        """
        This function is used to ping all hosts in the network, except for the router and the switch.
        It uses the ping command to send an ICMP echo request to each host, and prints out the results.
        """

        for host in self.net.hosts:
            for host2 in self.net.hosts:
                if host2!= host and "r" not in host.name and "r" not in host2.name:
                    print(f"{host.name} pinging {host2.name}")

                    print(host.cmd(f"ping6 -c 1 -v {entry_finder(name=host2.name, entries=self.pyhosts.entries)[0].address}"))

    def code_brain(self):
        node = self.net.getNodeByName("h14")
        router = self.net.getNodeByName("r5")
        # print(host.cmd('ip -6 route'))
        print("**h14**")
        print(node.cmd("ifconfig -a"))
        print("*Route*")
        print(node.cmd("ip -6 route show"))
        print(node.cmd("ip -6 neigh show"))
        print("**r5**")
        print(router.cmd("ifconfig -a"))
        print(router.cmd("ip -6 neigh show"))
        print(router.cmd('vtysh -c "sh isis neighbor"'))
        # print("*Route*")
        # print(router.cmd("ip -6 route show"))
        # print(router.cmd("systemctl status firewalld"))
        # print(router.cmd("systemctl status zebra"))
        # print(router.cmd("systemctl status isisd"))
        print("pinging h14 from r5")
        print(node.cmd(f"ping6 -c 1 -v fcff:5::1"))
        print("Tracing")
        print(node.cmd(f"traceroute6 -n fd00:16::2"))
        print(node.cmd(f"ping6 -c 1 -v {entry_finder(name=router.name, entries=self.pyhosts.entries)[0].address}"))
        sleep(300)
