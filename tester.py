from segment_route import entry_finder, ETC_HOSTS_FILE
from python_hosts import Hosts
from time import sleep
from segment_route import MetricCollector, SegmentRouter
from multiprocessing import Process

class TestSuite:
    """
    This class is used to test the Segment Routing network.
    """

    def __init__(self, net):
        """
        This function initializes the network and the processes.

        Args:
            net (Mininet): The Mininet network object.
        """
        self.net = net  # The Mininet network object
        self.pyhosts = Hosts()  # The python-hosts object
        self.pyhosts.import_file(ETC_HOSTS_FILE)  # Reads the /etc/hosts file
        self.metrics_brain = MetricCollector(self.net)  # The MetricCollector object
        self.router = SegmentRouter(self.net, self.metrics_brain)  # The SegmentRouter object
        metric_checker = Process(target=self.check_metrics, args=())  # The process for checking metrics
        cli_runner = Process(target=self.run_tester, args=())  # The process for running the tester
        metric_checker.start()  # Starts the metric checker process
        cli_runner.start()  # Starts the CLI runner process
        metric_checker.join()  # Waits for the metric checker process to finish
        cli_runner.join()  # Waits for the CLI runner process to finish

    def check_metrics(self):
        """
        This function is used to check the metrics in the Multiprocessing.
        """
        while True:
            self.metrics_brain.collect_all_usage()  # Collects the metrics
            sleep(60)  # Sleeps for 60 seconds

    def run_tester(self):
        """
        This function is used to run the tester in the Multiprocessing.
        """
        sleep(60)  # Sleeps for 60 seconds
        while True:
            self.custom_pinger()  # Runs the custom pinger

    def ping_all(self):
        """
        This function is used to ping all hosts in the network.
        """
        self.net.pingAll()  # Pings all hosts

    def custom_pinger(self):
        """
        This function is used to ping all hosts in the network, except for the router and the switch.
        It uses the ping command to send an ICMP echo request to each host, and prints out the results.
        """
        for host in self.net.hosts:
            for host2 in self.net.hosts:
                if host2!= host and "r" not in host.name and "r" not in host2.name:
                    self.router.route_route(host, host2)  # Routes the packets through the SegmentRouter
                    host.cmd(f"ping6 -c 1 -v {entry_finder(name=host2.name, entries=self.pyhosts.entries)[0].address}")  # Pings the other host

    def code_brain(self):
        """
        This function is used to test the code and understand the functionality.
        It executes various commands on the nodes and the router to check the network configuration and connectivity.
        This code only works with Debug enable and it is in order to check what is happening with the segment routing network.
        """
        node = self.net.getNodeByName("h14")
        router = self.net.getNodeByName("r5")
        node.cmd("ifconfig -a")
        node.cmd("ip -6 route show")
        node.cmd("ip -6 neigh show")
        router.cmd("ifconfig -a")
        router.cmd("ip -6 neigh show")
        router.cmd('vtysh -c "sh isis neighbor"')

        router.cmd("ip -6 route show")
        router.cmd("systemctl status firewalld")
        router.cmd("systemctl status zebra")