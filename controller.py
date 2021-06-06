#! python3

import os
import sys
# import MySQLdb
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


class Controller():
    def __init__(self):
        self.SWITCH_NUM = 0
        self.TOR_LIST = {}  # switch.name:host_ipv6
        self.TOPO_FILE = "/int/topo/tree_topo"
        # self.TOPO_FILE = "/int/topo/line_topo"
        # self.TOPO_FILE = "/int/topo/leaf_spine_topo"
        # self.TOPO_FILE = "/int/topo/test_ipv6_topo"
        self.GRAPH = nx.Graph()
        self.LAYERS = []
        self.LAYER_NUMBER = 0
        self.LINK_LIST = self.readTopoFile()
        self.SWITCH_LIST = self.switchConnect()
        self.DOWNSTREAM_GROUP_HANDLE = {}
        self.UPSTREAM_GROUP_HANDLE = {}
        self.DOWNSTREAM_MEMBER_HANDLE = {}
        self.UPSTREAM_MEMBER_HANDLE = {}
        self.MC_GROUP_HANDLE = {}
        self.ENTRY_HDL_MAP = None
        self.TRANSMIT_NODE_DELAY = {}  # Switch Instance

    def switchConnect(self):
        # try:
        self.SWITCH_NUM = int(
            os.popen(
                "netstat -tunlp | grep simple_switch | wc -l").readlines()[0])
        print("Now has %d switches" % self.SWITCH_NUM)
        switch_list = []
        for index in range(self.SWITCH_NUM):
            sw = SWITCH(9000 + index, "127.0.0.1")
            # print("has ports %s" % (self.LINK_LIST[str(index)].keys()))
            for port in self.LINK_LIST[str(index)].keys():
                print("port is %s" % port)
                try:
                    ipv6 = netifaces.ifaddresses(port)[
                        netifaces.AF_INET6][0]['addr']
                    ipv4 = None
                    ipv6 = ipv6.split("%")[0]
                except KeyError:
                    ipv4 = netifaces.ifaddresses(port)[
                        netifaces.AF_INET][0]['addr']
                    ipv6 = None
                sw._port_map(port, ipv6, ipv4,
                             self.LINK_LIST[str(index)][port])
            switch_list.append(sw)
            # print("s%s description: %s" % (str(index), sw._description()))
        # except:
        #     print("connect error")
        return switch_list

    def readTopoFile(self):
        with open(self.TOPO_FILE, "r") as f:
            cmds = f.readlines()
        tors = cmds[:3][0][:-1].split(":")[-1]
        core = cmds[:3][1][:-1].split(":")[-1]
        if tors != "":
            tors = [_[1:] for _ in tors.split(",")]
            sws = tors
        if core != "":
            core = [_[1:] for _ in core.split(",")]
            sws = sws + core
        print(tors)
        print(core)
        if len(tors) > 0:
            for sw_index in tors:
                try:
                    ip = getHostIpv6FromIndex(sw_index)
                except KeyError:
                    ip = getHostIpv4FromIndex(sw_index)
                self.TOR_LIST[sw_index] = [ip, getHostMacFromIndex(sw_index)]

        # print(sws)
        nodes = [str("s" + str(i)) for i in sws]
        color_map = {}
        for sw in sws:
            s_name = "s" + str(sw)
            if sw in tors:
                color_map[s_name] = 'red'
            else:
                color_map[s_name] = 'green'
        self.GRAPH.add_nodes_from(nodes)
        colors = [color_map.get(node, 0.25) for node in self.GRAPH.nodes()]
        # print("color_map has %s" % color_map)
        # print("colors has %s" % colors)
        self.LAYER_NUMBER = int(cmds[:3][2][:-1].split(":")[-1])
        for n in range(self.LAYER_NUMBER):
            self.LAYERS.append(
                cmds[3:3 +
                     self.LAYER_NUMBER][n][:-1].split(":")[-1].split(","))
        print("********** layers has: %s", self.LAYERS)
        links = dict(zip(sws, [{} for _ in sws]))
        topo = cmds[3 + self.LAYER_NUMBER:]
        edges = []
        for t in topo:
            s1 = t[:-1].split("-")[0]
            s2 = t[:-1].split("-")[1]
            edges.append((s1.split(":")[0], s2.split(":")[0]))
            s1_name = s1.split(":")[0][1:]
            s1_iface = s1.split(":")[1]
            s2_name = s2.split(":")[0][1:]
            s2_iface = s2.split(":")[1]
            s1_point = "s%s-eth%s" % (s1_name, s1_iface)
            s2_point = "s%s-eth%s" % (s2_name, s2_iface)
            links[s1_name][s1_point] = s2_point
            links[s2_name][s2_point] = s1_point
        self.GRAPH.add_edges_from(edges)
        nx.draw(
            self.GRAPH,
            # cmap=plt.get_cmap('viridis'),
            with_labels=True,
            node_color=colors,
            font_color='white',
        )
        plt.savefig("topo_graph.png")
        plt.show()
        return links

    # IngressPipeImpl.ndp_reply_table(hdr.ndp.target_ipv6_addr)
    def writeNdpNsReply(self, switch, targetIpv6Addr, targetMac):
        info = switch.table_add_exact(table="IngressPipeImpl.ndp_reply_table",
                                      match_key=[str(targetIpv6Addr)],
                                      match_key_types=['ipv6'],
                                      action="IngressPipeImpl.ndp_ns_to_na",
                                      runtime_data=[str(targetMac)],
                                      runtime_data_types=['mac'])
        print("Insert ndp_reply_table on %s successfully: %s" %
              (switch.name, info))
        return info

    def writeNdpRsReply(self, switch, targetIpv6Addr, targetMac):
        info = switch.table_add_exact(table="IngressPipeImpl.ndp_reply_table",
                                      match_key=[str(targetIpv6Addr)],
                                      match_key_types=['ipv6'],
                                      action="IngressPipeImpl.ndp_rs_to_ra",
                                      runtime_data=[str(targetMac)],
                                      runtime_data_types=['mac'])
        print("Insert ndp_reply_table on %s successfully: %s" %
              (switch.name, info))
        return info

    # IngressPipeImpl.rmac(hdr.ethernet.dst_addr)
    # only a counter counting how many l2 packet reach here
    # same as rmac.hit()
    def writeRmacTable(self, switch, ethDstAddr):
        info = switch.table_add_exact(table="IngressPipeImpl.rmac",
                                      match_key=[str(ethDstAddr)],
                                      match_key_types=['mac'],
                                      action="NoAction",
                                      runtime_data=[],
                                      runtime_data_types=[])
        print("Insert rmac on %s successfully: %s" % (switch.name, info))
        return info

    # IngressPipeImpl.srv6_my_sid(hdr.ipv6.dst_addr)
    def writeSRv6MySidTable(self, switch, localIpv6Addr):
        info = switch.table_add_exact(table="IngressPipeImpl.srv6_my_sid",
                                      match_key=[str(localIpv6Addr)],
                                      match_key_types=['ipv6'],
                                      action="IngressPipeImpl.srv6_end",
                                      runtime_data=[],
                                      runtime_data_types=[])
        print("Insert srv6_my_sid on %s successfully: %s" %
              (switch.name, info))
        return info

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

    def writeSRv4Transit2SegmentsTable(self, sw, dstIpv4Addr, segmentList2):
        info = sw.table_add_exact(table="IngressPipeImpl.srv4_transit",
                                  match_key=[str(dstIpv4Addr)],
                                  match_key_types=['ipv4'],
                                  action="IngressPipeImpl.srv4_t_insert_2",
                                  runtime_data=segmentList2,
                                  runtime_data_types=['8', '8'])
        print("Insert srv4_transit insert_2 on %s successfully: %s" %
              (sw.name, info))
        return info

    def writeSRv4Transit3SegmentsTable(self, sw, dstIpv4Addr, segmentList3):
        info = sw.table_add_exact(table="IngressPipeImpl.srv4_transit",
                                  match_key=[str(dstIpv4Addr)],
                                  match_key_types=['ipv4'],
                                  action="IngressPipeImpl.srv4_t_insert_3",
                                  runtime_data=segmentList3,
                                  runtime_data_types=['8', '8', '8'])
        print("Insert srv4_transit insert_3 on %s successfully: %s" %
              (sw.name, info))
        return info

    # IngressPipeImpl.l2_exact_table(hdr.ethernet.dst_addr)
    def writeL2ExactTable(self, switch, ethDstAddr, egressPort):
        # print("switch = %s, ethDstAddr = %s, egressPort = %d" %
        #       (switch.name, ethDstAddr, egressPort))
        info = switch.table_add_exact(table="IngressPipeImpl.l2_exact_table",
                                      match_key=[str(ethDstAddr)],
                                      match_key_types=['mac'],
                                      action="IngressPipeImpl.set_egress_port",
                                      runtime_data=[str(egressPort)],
                                      runtime_data_types=['9'])
        print("Insert l2_exact_table on %s successfully: %s" %
              (switch.name, info))
        return info

    def createL2MulticastGroup(self, switch, gid, ports):
        mgrp_hdl, l1_hdl, message = switch.multicast_group_create(gid=gid,
                                                                  rid=0,
                                                                  ports=ports,
                                                                  lags=ports)
        print("Create multicast group on %s successfully: %s" %
              (switch.name, str(str(mgrp_hdl) + str(l1_hdl) + str(message))))
        return mgrp_hdl, l1_hdl, message

    # IngressPipeImpl.l2_ternary_table(hdr.ethernet.dst_addr)
    def writeL2TernaryTable(self, switch, ethDstAddr, ethMask, multicastGroup):
        info = switch.table_add_ternary(
            table="IngressPipeImpl.l2_ternary_table",
            match_key=[ethDstAddr, ethMask],
            match_key_types=['mac', '48'],
            action="IngressPipeImpl.set_multicast_group",
            runtime_data=[str(multicastGroup)],
            runtime_data_types=['32'],
            priority=10)
        print("Insert l2_ternary_table on %s successfully: %s" %
              (switch.name, info))
        return info

    # IngressPipeImpl.acl_table(standard_metadata.ingress_port)
    def writeAclTable(self, switch, ingressPort, ethDstAddr, ethSrcAddr,
                      ethType, ipProto, icmpType, l4DstPort, l4SrcPort):
        info = switch.table_add_ternary(
            table="IngressPipeImpl.acl_table",
            match_key=[
                str(ingressPort),
                str(ethDstAddr),
                str(ethSrcAddr),
                str(ethType),
                str(ipProto),
                str(icmpType),
                str(l4DstPort),
                str(l4SrcPort)
            ],
            match_key_types=['9', 'mac', 'mac', '16', '8', '8', '16', '16'],
            action="IngressPipeImpl.send_to_cpu",
            runtime_data=[],
            runtime_data_types=[])
        print("Insert acl_table on %s successfully: %s" % (switch.name, info))
        return info

    # IngressPipeImpl.ecmp_routing_v6_table(hdr.ipv6.dst_addr)
    def writeDirectRoutingIpv6Table(self, switch, dstIpv6Addr, nextHopMac):
        info = switch.table_add_exact(
            table="IngressPipeImpl.direct_routing_v6_table",
            match_key=[dstIpv6Addr],
            match_key_types=['ipv6'],
            action="IngressPipeImpl.set_next_hop",
            runtime_data=[str(nextHopMac)],
            runtime_data_types=['mac'])
        print("Insert direct_routing_v6_table on %s successfully: %s" %
              (switch.name, info))
        return info

    def writeEcmpGroupRoutingIpv6Table(self, switch, dstIpv6Addr, grp_handle):
        print("switch is %s, dstIpv6Addr is %s, grp_handle is %s" %
              (switch.name, dstIpv6Addr, grp_handle))
        info = switch.add_exact_entry_to_group(
            table_name="IngressPipeImpl.ecmp_routing_v6_table",
            match_key=[dstIpv6Addr],
            match_key_types=["ipv6"],
            grp_handle=int(grp_handle))
        print("Insert ecmp_routing_v6_table on %s successfully: %s" %
              (switch.name, info))
        return info

    def writeEcmpHostRoutingIpv6Table(self, switch, dstIpv6Addr, grp_handle):
        print("To host: switch is %s, dstIpv6Addr is %s, grp_handle is %s" %
              (switch.name, dstIpv6Addr, grp_handle))
        info = switch.add_exact_entry_to_group(
            table_name="IngressPipeImpl.ecmp_routing_v6_table",
            match_key=[dstIpv6Addr],
            match_key_types=["ipv6"],
            grp_handle=int(grp_handle))
        print("Insert ecmp_routing_v6_table on %s successfully: %s" %
              (switch.name, info))
        return info

    def writeDirectRoutingIpv4Table(self, switch, dstIpv4Addr, nextHopMac):
        info = switch.table_add_exact(
            table="IngressPipeImpl.direct_routing_v4_table",
            match_key=[dstIpv4Addr],
            match_key_types=['ipv4'],
            action="IngressPipeImpl.set_next_hop",
            runtime_data=[str(nextHopMac)],
            runtime_data_types=['mac'])
        print("Insert direct_routing_v4_table on %s successfully: %s" %
              (switch.name, info))
        return info

    def writeEcmpGroupRoutingIpv4Table(self, switch, dstIpv4Addr, grp_handle):
        print("switch is %s, dstIpv4Addr is %s, grp_handle is %s" %
              (switch.name, dstIpv4Addr, grp_handle))
        info = switch.add_exact_entry_to_group(
            table_name="IngressPipeImpl.ecmp_routing_v4_table",
            match_key=[dstIpv4Addr],
            match_key_types=["ipv4"],
            grp_handle=int(grp_handle))
        print("Insert ecmp_routing_v4_table on %s successfully: %s" %
              (switch.name, info))
        return info

    def writeEcmpHostRoutingIpv4Table(self, switch, dstIpv4Addr, grp_handle):
        print("To host: switch is %s, dstIpv4Addr is %s, grp_handle is %s" %
              (switch.name, dstIpv4Addr, grp_handle))
        info = switch.add_exact_entry_to_group(
            table_name="IngressPipeImpl.ecmp_routing_v4_table",
            match_key=[dstIpv4Addr],
            match_key_types=["ipv4"],
            grp_handle=int(grp_handle))
        print("Insert ecmp_routing_v4_table on %s successfully: %s" %
              (switch.name, info))
        return info

    def createHostEcmpGroup(self, switch, mac):
        grp_hdl = switch.create_group("IngressPipeImpl.ecmp_selector")

        mbr_hdl = switch.act_prof_add_member(
            action_profile_name="IngressPipeImpl.ecmp_selector",
            action_name="IngressPipeImpl.set_next_hop",
            runtime_data=[mac],
            runtime_data_types=['mac'])

        switch.add_member_to_group(
            action_profile_name="IngressPipeImpl.ecmp_selector",
            mbr_handle=mbr_hdl,
            grp_handle=grp_hdl)
        return grp_hdl

    def createEcmpSelectorGroup(self, switch, downstreamGroupSwitches,
                                upstreamGroupSwitches):
        if len(downstreamGroupSwitches) > 0:
            downstream_grp_handle = switch.create_group(
                "IngressPipeImpl.ecmp_selector")
            self.DOWNSTREAM_GROUP_HANDLE[str(
                switch.name)] = downstream_grp_handle
            print("Create ecmp_selector group on %s successfully: downstream \
                    group is %s"                                                                                                 % (switch.name, downstream_grp_handle))
            # add downstream switches to member
            for i in range(len(downstreamGroupSwitches)):
                info = switch.act_prof_add_member(
                    action_profile_name="IngressPipeImpl.ecmp_selector",
                    action_name="IngressPipeImpl.set_next_hop",
                    runtime_data=[str(downstreamGroupSwitches[i].mgr_mac)],
                    runtime_data_types=['mac'])
                self.DOWNSTREAM_MEMBER_HANDLE[str(switch.name)] = info
                print(
                    "Add switch %s to downstream group on %s successfully: %s"
                    % (downstreamGroupSwitches[i].name, switch.name, info))
                switch.add_member_to_group(
                    action_profile_name="IngressPipeImpl.ecmp_selector",
                    mbr_handle=self.DOWNSTREAM_MEMBER_HANDLE[str(switch.name)],
                    grp_handle=self.DOWNSTREAM_GROUP_HANDLE[str(switch.name)])

        if len(upstreamGroupSwitches) > 0:
            # print("upstreamGroupSwitches is %s" % upstreamGroupSwitches)
            upstream_grp_handle = switch.create_group(
                "IngressPipeImpl.ecmp_selector")
            self.UPSTREAM_GROUP_HANDLE[str(switch.name)] = upstream_grp_handle
            print(
                "Create ecmp_selector group on %s successfully: upstream is %s"
                % (switch.name, upstream_grp_handle))
            # add upstream switches to member
            for i in range(len(upstreamGroupSwitches)):
                info = switch.act_prof_add_member(
                    action_profile_name="IngressPipeImpl.ecmp_selector",
                    action_name="IngressPipeImpl.set_next_hop",
                    runtime_data=[str(upstreamGroupSwitches[i].mgr_mac)],
                    runtime_data_types=['mac'])
                self.UPSTREAM_MEMBER_HANDLE[str(switch.name)] = info
                print(
                    "Add switch %s to upstream group on %s successfully: %s" %
                    (upstreamGroupSwitches[i].name, switch.name, info))
                switch.add_member_to_group(
                    action_profile_name="IngressPipeImpl.ecmp_selector",
                    mbr_handle=self.UPSTREAM_MEMBER_HANDLE[str(switch.name)],
                    grp_handle=self.UPSTREAM_GROUP_HANDLE[str(switch.name)])

    def deleteAllEntries(self):
        for sw in self.SWITCH_LIST:
            for table in [
                    "IngressPipeImpl.ndp_reply_table", "IngressPipeImpl.rmac",
                    "IngressPipeImpl.srv6_my_sid",
                    "IngressPipeImpl.srv6_transit",
                    "IngressPipeImpl.l2_exact_table",
                    "IngressPipeImpl.l2_ternary_table",
                    "IngressPipeImpl.acl_table",
                    "IngressPipeImpl.ecmp_routing_v6_table",
                    "IngressPipeImpl.direct_routing_v6_table"
            ]:
                entries = sw.table_get(table)
                for e in entries:
                    entry_handle = getEntryHandle(str(e))
                    sw.table_delete(table, entry_handle)

    def deleteGroups(self, switch):
        if switch in self.GROUP_HANDLE.keys():
            switch.delete_group("IngressPipeImpl.ecmp_selector",
                                self.GROUP_HANDLE[str(switch.name)])
        self.GROUP_HANDLE.pop(switch.name)
        print("Delete all groups in %s successfully." % switch.name)

    def deleteEntries(self, switch):
        for table in self.ENTRY_HDL_MAP.keys():
            if len(self.ENTRY_HDL_MAP.get(table)) == 0:
                continue
            for entry_handle in self.ENTRY_HDL_MAP.get(table):
                try:
                    switch.table_delete(table, entry_handle)
                except Exception as e:
                    raise (
                        "Delete %s %s failed, with error %s and traceback %s" %
                        (table, switch.name, e, traceback.format_exc()))
        print("Delete all entries in %s successfully." % switch.name)

    def insertNormalEntries(self):
        for sw in self.SWITCH_LIST:
            print("*" * 40)
            self.ENTRY_HDL_MAP = {
                "IngressPipeImpl.ndp_reply_table": [],
                "IngressPipeImpl.rmac": [],
                "IngressPipeImpl.srv6_my_sid": [],
                "IngressPipeImpl.srv6_transit": [],
                "IngressPipeImpl.l2_exact_table": [],
                "IngressPipeImpl.l2_ternary_table": [],
                "IngressPipeImpl.acl_table": [],
                "IngressPipeImpl.ecmp_routing_v6_table": [],
                "IngressPipeImpl.direct_routing_v6_table": []
            }
            entry_hdl = self.writeRmacTable(sw, sw.mgr_mac)
            self.ENTRY_HDL_MAP["IngressPipeImpl.rmac"].append(entry_hdl)

            entry_hdl = self.writeL2ExactTable(sw, sw.mgr_mac, MGR_PORTNUM)
            self.ENTRY_HDL_MAP["IngressPipeImpl.l2_exact_table"].append(
                entry_hdl)

            entry_hdl = self.writeNdpNsReply(sw, sw.mgr_ipv6, sw.mgr_mac)
            self.ENTRY_HDL_MAP["IngressPipeImpl.ndp_reply_table"].append(
                entry_hdl)

            if str(sw.index) in self.TOR_LIST.keys():
                host_ipv6 = getHostIpv6FromIndex(sw.index)
                host_mac = getHostMacFromIndex(sw.index)
                print("localhost_ipv6 = %s, localost_mac = %s" %
                      (host_ipv6, host_mac))
                entry_hdl = self.writeNdpNsReply(sw, host_ipv6, host_mac)
                self.ENTRY_HDL_MAP["IngressPipeImpl.ndp_reply_table"].append(
                    entry_hdl)

                entry_hdl = self.writeL2ExactTable(sw, host_mac, TIN_PORTNUM)
                self.ENTRY_HDL_MAP["IngressPipeImpl.l2_exact_table"].append(
                    entry_hdl)

                group_hdl = self.createHostEcmpGroup(
                    sw,
                    self.TOR_LIST.get(str(sw.index))[1])
                entry_hdl = self.writeEcmpHostRoutingIpv6Table(
                    sw,
                    self.TOR_LIST.get(str(sw.index))[0], group_hdl)
                self.ENTRY_HDL_MAP[
                    "IngressPipeImpl.ecmp_routing_v6_table"].append(entry_hdl)

            upstream_ecmp_group = []
            downstream_ecmp_group = []
            print("%s nexthop has: %s" % (sw.name, sw.next_hop))
            for port in sw.next_hop.keys():
                next_hop_port = sw.next_hop[port]
                neighbor = getSwitchInstanceFromPort(self.SWITCH_LIST,
                                                     next_hop_port)
                entry_hdl = self.writeL2ExactTable(sw, neighbor.mgr_mac,
                                                   port.split("eth")[1])
                self.ENTRY_HDL_MAP["IngressPipeImpl.l2_exact_table"].append(
                    entry_hdl)

                # set ecmp group
                if str(neighbor.index) in self.TOR_LIST.keys():
                    entry_hdl = self.writeDirectRoutingIpv6Table(
                        sw,
                        self.TOR_LIST.get(str(neighbor.index))[0],
                        neighbor.mgr_mac)
                    self.ENTRY_HDL_MAP[
                        "IngressPipeImpl.direct_routing_v6_table"].append(
                            entry_hdl)
                else:
                    if sw.index < neighbor.index:
                        upstream_ecmp_group.append(
                            getSwitchInstanceFromPort(self.SWITCH_LIST,
                                                      next_hop_port))
                    elif sw.index > neighbor.index:
                        downstream_ecmp_group.append(
                            getSwitchInstanceFromPort(self.SWITCH_LIST,
                                                      next_hop_port))
            # self.deleteEntries(sw)
            sw_layer = getLayerFromIndex(self.LAYERS, sw.index)
            # print("sw_layer = %d" % sw_layer)
            print("upstream_ecmp_group has %s, downstream_ecmp_group has %s" %
                  (upstream_ecmp_group, downstream_ecmp_group))
            if len(upstream_ecmp_group) > 0 or len(downstream_ecmp_group) > 0:
                self.createEcmpSelectorGroup(sw, downstream_ecmp_group,
                                             upstream_ecmp_group)
                if len(upstream_ecmp_group
                       ) > 0 and sw_layer != self.LAYER_NUMBER - 2:
                    for dst_index in range(
                            int(sw.index) + 1, int(self.SWITCH_NUM)):
                        dst_layer = getLayerFromIndex(self.LAYERS, dst_index)
                        if dst_layer == sw_layer:
                            continue
                        entry_hdl = self.writeEcmpGroupRoutingIpv6Table(
                            sw,
                            getSwitchInstanceFromIndex(self.SWITCH_LIST,
                                                       dst_index).mgr_ipv6,
                            self.UPSTREAM_GROUP_HANDLE[sw.name])
                        self.ENTRY_HDL_MAP[
                            "IngressPipeImpl.ecmp_routing_v6_table"].append(
                                entry_hdl)

                if len(downstream_ecmp_group) > 0 and sw_layer != 1:
                    for dst_index in range(int(sw.index)):
                        dst_layer = getLayerFromIndex(self.LAYERS, dst_index)
                        if dst_layer == sw_layer:
                            continue
                        entry_hdl = self.writeEcmpGroupRoutingIpv6Table(
                            sw,
                            getSwitchInstanceFromIndex(self.SWITCH_LIST,
                                                       dst_index).mgr_ipv6,
                            self.DOWNSTREAM_GROUP_HANDLE[sw.name])
                        self.ENTRY_HDL_MAP[
                            "IngressPipeImpl.ecmp_routing_v6_table"].append(
                                entry_hdl)

                for sw_index in self.TOR_LIST.keys():
                    if str(sw_index) != str(sw.index):
                        host_ipv6 = getHostIpv6FromIndex(str(sw_index))
                        if int(sw_index) < int(
                                sw.index) and len(downstream_ecmp_group) > 0:
                            entry_hdl = self.writeEcmpHostRoutingIpv6Table(
                                sw, host_ipv6,
                                self.DOWNSTREAM_GROUP_HANDLE[sw.name])
                            self.ENTRY_HDL_MAP[
                                "IngressPipeImpl.ecmp_routing_v6_table"].append(
                                    entry_hdl)
                        elif int(sw_index) > int(
                                sw.index) and len(upstream_ecmp_group) > 0:
                            entry_hdl = self.writeEcmpHostRoutingIpv6Table(
                                sw, host_ipv6,
                                self.UPSTREAM_GROUP_HANDLE[sw.name])
                            self.ENTRY_HDL_MAP[
                                "IngressPipeImpl.ecmp_routing_v6_table"].append(
                                    entry_hdl)

            # for sw_index in self.TOR_LIST.keys():
            #     if str(sw_index) != str(sw.index):
            #         host_ipv6 = getHostIpv6FromIndex(str(sw_index))
            #             if int(sw_index) < int(sw.index):
            #                 entry_hdl = self.writeDirectRoutingIpv6Table(
            #                     sw, host_ipv6,
            #                     self.DOWNSTREAM_GROUP_HANDLE[sw.name])
            # self.deleteEntries(sw)
            # self.deleteGroups(sw)

    def CalculateTransmitNodes(self):
        for i in range(12, 24):
            self.TRANSMIT_NODE_DELAY[str(i)] = MAX_INT

    def CalculateStaticNodes(self):
        pass

    def CalculateSegmentList(self, src, dst):
        print("#" * 10 + " Calculating Segment List " + "#" * 10)
        segment_list = [getSwitchInstanceFromIndex(dst).mgr_ipv6]
        min_delay_sw = None
        min_delay = MAX_INT
        for sw in range(self.TRANSMIT_NODE_DELAY):
            print("Delay Register Calculating: sw%d" % (sw.index))
            delay = 0
            for p in range(sw.port_ipv6.keys()):
                print(p)
                p = p.split("eth")[1]
                delay += self.getDelayRegister(sw, p)
            delay /= len(sw.port_ipv6.keys())
            if delay < min_delay:
                min_delay_sw = sw
            self.TRANSMIT_NODE_DELAY[sw] = int(delay)
        segment_list.append(min_delay_sw.mgr_ipv6)
        return segment_list

    def insertSRv6Entries(self):
        # src and dst is sw.index in str
        for sw in self.SWITCH_LIST:
            # SRv6 Tables
            entry_hdl = self.writeSRv6MySidTable(sw, sw.mgr_ipv6)
            self.ENTRY_HDL_MAP["IngressPipeImpl.srv6_my_sid"].append(entry_hdl)
        self.CalculateTransmitNodes()
        f = open(TRANSMIT_NODES_FILE, 'w')
        f.truncate()
        for sw_index in self.TRANSMIT_NODE_DELAY.keys():
            f.write("%s:" % sw_index)
            for port in getSwitchInstanceFromIndex(self.SWITCH_LIST,
                                                   sw_index).next_hop.keys():
                print(port)
                f.write("%s" % port.split("eth")[1])
                f.write(" ")
            f.write("\n")
        print("#" * 30 + " Write transmit nodes to file successfully! " +
              "#" * 30)
        f.close()
        # src_sw = getSwitchInstanceFromIndex(src)
        # # dst_sw = getSwitchInstanceFromIndex(dst)
        # dst_host_ipv6 = getHostIpv6FromIndex(dst)
        # segment_list = self.CalculateSegmentList(src, dst)
        # self.writeSRv6Transit2SegmentsTable(src_sw, dst_host_ipv6,
        #                                     segment_list)

    def controllerMain(self):
        print("Controller connecting to switches ...")
        # self.deleteAllEntries()
        # Static Entries
        self.insertNormalEntries()
        # self.CalculateTransmitNodes()
        # Dynamic Entries
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


def getSwitchInstanceFromIndex(sw_list, index):
    for sw in sw_list:
        if sw.index == int(index):
            return sw


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


def initSQLsToDateBase(sql_list):
    db = MySQLdb.connect(host="127.0.0.1",
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
    c = Controller()
    c.controllerMain()