import influxdb_client, os, time
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

TOKEN = "F4zRspwXci5PlMgswkhT2eDy-hNfxVHzFtFRlNjx0F4EKz95BfhC-2BQadv-S7ZdlwwfbhTFs8gWI_6IjHS01Q=="
ORG = "srv6"
URL = "http://localhost:8086"

def dump_to_Influx(operation_mode, dataset, topo, size):
    bucket = operation_mode
    write_client = influxdb_client.InfluxDBClient(url=URL, token=TOKEN, org=ORG)

    write_api = write_client.write_api(write_options=SYNCHRONOUS)

    for node in dataset.keys():
        point = Point(node).tag("topology", topo).tag("size", size).field("cpu_usage", dataset[node]["cpu_usage"])
        write_api.write(bucket=bucket, org=ORG, record=point)
        point = Point(node).tag("topology", topo).tag("size", size).field("memory_usage", dataset[node]["memory_usage"])
        write_api.write(bucket=bucket, org=ORG, record=point)
