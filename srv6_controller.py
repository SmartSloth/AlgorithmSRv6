#! python3

import os
import sys
import argparse
import pymysql
import traceback
import netifaces
import networkx as nx
import matplotlib.pyplot as plt

import include.runtimedata
from include.class_define import SWITCH, thrift_connect

MGR_PORTNUM = 15
TIN_PORTNUM = 7
DEFAULT_BROADCAST_GROUP_ID = 1
DEFAULT_HOST_ECMP_GROUP = 5
MAX_PORT_NUM = 8
MAX_INT = 2**32-1
TRANSMIT_NODES_FILE = "/int/transmit_node.txt"
parser = argparse.ArgumentParser()
parser.add_argument("-s",
                    "--src-host",
                    help="src host",
                    default="0")
parser.add_argument("-d",
                    "--dst-host",
                    help="dst host",
                    default="35")
args = parser.parse_args()
SRC_HOST = args.src_host
DST_HOST = args.dst_host


class SRv6Controller():
    def __init__(self):
        self.SWITCH_PORT_LIST = {}
        self.SRC_SWITCH = getSwitchInstanceFromIndex(SRC_HOST)
        self.DST_SWITCH = getSwitchInstanceFromIndex(DST_HOST)
        self.TRANSMIT_NODE_DELAY = {}  # Switch Instance
        self.switchConnect()

    def switchConnect(self):
        f = open(TRANSMIT_NODES_FILE, 'r')
        for line in f.readlines():
            line = line.strip()
            index = int(line.split(":")[0])
            sw = SWITCH(9000 + int(index), "127.0.0.1")
            ports = line.split(":")[1].split()
            self.SWITCH_PORT_LIST[sw] = ports
            self.TRANSMIT_NODE_DELAY[sw] = MAX_INT
        f.close()

    # IngressPipeImpl.srv6_transit(hdr.ipv6.dst_addr)
    def writeSRv6Transit2SegmentsTable(self, sw, dstIpv6Addr, segmentList2):
        info = sw.table_add_exact(table="IngressPipeImpl.srv6_transit",
                                  match_key=[str(dstIpv6Addr)],
                                  match_key_types=['ipv6'],
                                  action="IngressPipeImpl.srv6_t_insert_2",
                                  runtime_data=segmentList2,
                                  runtime_data_types=['ipv6', 'ipv6'])
        print("Insert srv6_transit insert_2 on %s successfully: %s" %
              (sw.name, info))
        return info

    def writeSRv6Transit3SegmentsTable(self, sw, dstIpv6Addr, segmentList3):
        info = sw.table_add_exact(table="IngressPipeImpl.srv6_transit",
                                  match_key=[str(dstIpv6Addr)],
                                  match_key_types=['ipv6'],
                                  action="IngressPipeImpl.srv6_t_insert_3",
                                  runtime_data=segmentList3,
                                  runtime_data_types=['ipv6', 'ipv6', 'ipv6'])
        print("Insert srv6_transit insert_3 on %s successfully: %s" %
              (sw.name, info))
        return info

    def Calculate2SegmentList(self):
        print("#" * 10 + " Calculating 2 Segment List " + "#" * 10)
        segment_list = [self.DST_SWITCH.mgr_ipv6]
        min_delay_sw = None
        min_delay = MAX_INT
        for sw in self.TRANSMIT_NODE_DELAY.keys():
            print("Delay Register Calculating: sw%d" % (sw.index))
            delay = 0
            # print(sw._description())
            port_num = len(self.SWITCH_PORT_LIST.get(sw))
            for p in self.SWITCH_PORT_LIST.get(sw):
                delay += getDelayRegister(sw, int(p))
            delay = delay / port_num
            if delay < min_delay:
                min_delay_sw = sw
            self.TRANSMIT_NODE_DELAY[sw] = int(delay)
        segment_list.append(min_delay_sw.mgr_ipv6)
        print(segment_list)
        return segment_list

    def Calculate3SegmentList(self, dst):
        print("#" * 10 + " Calculating 3 Segment List " + "#" * 10)
        segment_list = [getSwitchInstanceFromIndex(dst).mgr_ipv6]
        return segment_list

    def clearAllSwitchSRv6TransitEntries(self):
        for sw in self.TRANSMIT_NODE_DELAY.keys():
            sw.clear_table("IngressPipeImpl.srv6_transit")

    def insertSRv6Entries(self):
        dst_mgr_ipv6 = self.DST_SWITCH.mgr_ipv6
        dst_trf_ipv6 = dst_mgr_ipv6.rsplit(":", 1)[0] + ":101"
        self.SRC_SWITCH.clear_table("IngressPipeImpl.srv6_transit")

        handle = self.writeSRv6Transit2SegmentsTable(
            self.SRC_SWITCH, dst_trf_ipv6, self.Calculate2SegmentList())
        sql = 'INSERT INTO entry (device_index, table_name, entry_handle, last_update) VALUES ("%d", "IngressPipeImpl.srv6_transit", "%s", NOW())' % (
            int(self.SRC_SWITCH.index), str(handle))
        insertSQLsToDateBase([sql])

    def controllerMain(self):
        print("Controller connecting to switches ...")
        self.insertSRv6Entries()


##########################################################################
#                             Util FUnctions                             #
##########################################################################
def getDelayRegister(sw, port):
    return sw.register_read("EgressPipeImpl.link_delay_register", port)


def getMacByPortName(port):
    return netifaces.ifaddresses(port)[netifaces.AF_LINK][0]['addr']


def getIpv6ByPortName(port):
    return netifaces.ifaddresses(port)[netifaces.AF_INET6][0]['addr'].split(
        "%")[0]


def getIpv4ByPortName(port):
    return netifaces.ifaddresses(port)[netifaces.AF_INET][0]['addr']


def getEntryHandle(entry):
    return int(
        str(entry).split("entry_handle=")[1].split(",")[0].split(")")[0])


def getSwitchMgrFromPort(port):
    return port.split("-")[0] + "-mgr"


def getSwitchInstanceFromPort(sw_list, port):
    for sw in sw_list:
        if str(sw.name) == str(port.split("-")[0]):
            return sw


def getSwitchInstanceFromIndex(index):
    return SWITCH(9000 + int(index), "127.0.0.1")


def nexthopToNeighbors(switch):
    neighbors = []
    for port in switch.next_hop.keys():
        neighbor = str(switch.next_hop.get(port)).split("-")[0]
        neighbors.append(neighbor)
    return list(set(neighbors))


def getHostIpv6FromIndex(index):
    mgr_ipv6 = getIpv6ByPortName(str("s" + str(index) + "-mgr"))
    # print(mgr_ipv6)
    trf_ipv6 = mgr_ipv6.rsplit(":", 1)[0] + ":101"
    return trf_ipv6


def getHostIpv4FromIndex(index):
    mgr_ipv4 = getIpv4ByPortName(str("s" + str(index) + "-mgr"))
    print(mgr_ipv4)
    trf_ipv4 = mgr_ipv4.rsplit(".", 1)[0] + ".1"
    return trf_ipv4


def getHostMacFromIndex(index):
    # host: 10:00:11:11:00:12 -> sw: 10:00:11:11:00:11
    mgr_mac = getMacByPortName(str("s" + str(index) + "-mgr"))
    trf_mac = mgr_mac.rsplit(":", 1)[0] + ":12"
    return trf_mac


def getLayerFromIndex(layers, index):
    for i in range(1, len(layers)):
        if int(layers[i - 1][0].split("s")[-1]) <= index and int(
                layers[i][0].split("s")[-1]) > index:
            return i - 1
    return i


def gethandl

def insertSQLsToDateBase(sql_list):
    db = pymysql.connect(host="127.0.0.1",
                         user="root",
                         passwd="123",
                         db="netinfo",
                         charset='utf8')
    cursor = db.cursor()
    for sql in sql_list:
        cursor.execute(sql)
    db.commit()
    db.close()


if __name__ == "__main__":
    c = SRv6Controller()
    c.controllerMain()