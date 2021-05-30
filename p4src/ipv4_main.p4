/*
 * Copyright 2019-present Open Networking Foundation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */


#include <core.p4>
#include <v1model.p4>

// CPU_PORT specifies the P4 port number associated to controller packet-in and
// packet-out. All packets forwarded via this port will be delivered to the
// controller as P4Runtime PacketIn messages. Similarly, PacketOut messages from
// the controller will be seen by the P4 pipeline as coming from the CPU_PORT.
#define CPU_PORT 255

// CPU_CLONE_SESSION_ID specifies the mirroring session for packets to be cloned
// to the CPU port. Packets associated with this session ID will be cloned to
// the CPU_PORT as well as being transmitted via their egress port (set by the
// bridging/routing/acl table). For cloning to work, the P4Runtime controller
// needs first to insert a CloneSessionEntry that maps this session ID to the
// CPU_PORT.
#define CPU_CLONE_SESSION_ID 99

// Maximum number of hops supported when using SRv4.
// Required for Exercise 7.
#define SRV4_MAX_HOPS 4
#define MAX_PORTS 16
// v1model: https://github.com/p4lang/p4c/blob/master/p4include/v1model.p4

typedef bit<9>   port_num_t;
typedef bit<48>  mac_addr_t;
typedef bit<16>  mcast_group_id_t;
typedef bit<32>  ipv4_addr_t;
typedef bit<16>  l4_port_t;
typedef bit<48>  time_t;
typedef bit<8>   srv4_sid_t;

const bit<16> ETHERTYPE_IPV4 = 0x0800;
const bit<16> ETHERTYPE_SRV4 = 0x2501;

const bit<8> IP_PROTO_ICMP   = 1;
const bit<8> IP_PROTO_TCP    = 6;
const bit<8> IP_PROTO_UDP    = 17;

const bit<8> NDP_OPT_TARGET_LL_ADDR = 2;

const bit<32> NDP_FLAG_ROUTER    = 0x80000000;
const bit<32> NDP_FLAG_SOLICITED = 0x40000000;
const bit<32> NDP_FLAG_OVERRIDE  = 0x20000000;


//------------------------------------------------------------------------------
// HEADER DEFINITIONS
//------------------------------------------------------------------------------

header ethernet_t {
    mac_addr_t  dst_addr;
    mac_addr_t  src_addr;
    bit<16>     ether_type;
}

header ipv4_t {
    bit<4>   version;
    bit<4>   ihl;
    bit<6>   dscp;
    bit<2>   ecn;
    bit<16>  total_len;
    bit<16>  identification;
    bit<3>   flags;
    bit<13>  frag_offset;
    bit<8>   ttl;
    bit<8>   protocol;
    bit<16>  hdr_checksum;
    bit<32>  src_addr;
    bit<32>  dst_addr;
}

header srv4h_t {
    bit<8>   last_entry;
    bit<8>   segment_left;
}

header srv4_list_t {
    srv4_sid_t  segment_id;
}

header tcp_t {
    bit<16>  src_port;
    bit<16>  dst_port;
    bit<32>  seq_no;
    bit<32>  ack_no;
    bit<4>   data_offset;
    bit<3>   res;
    bit<3>   ecn;
    bit<6>   ctrl;
    bit<16>  window;
    bit<16>  checksum;
    bit<16>  urgent_ptr;
}

header udp_t {
    bit<16> src_port;
    bit<16> dst_port;
    bit<16> len;
    bit<16> checksum;
}

header icmp_t {
    bit<8>   type;
    bit<8>   icmp_code;
    bit<16>  checksum;
    bit<16>  identifier;
    bit<16>  sequence_number;
    bit<64>  timestamp;
}

// Packet-in header. Prepended to packets sent to the CPU_PORT and used by the
// P4Runtime server (Stratum) to populate the PacketIn message metadata fields.
// Here we use it to carry the original ingress port where the packet was
// received.
@controller_header("packet_in")
header cpu_in_header_t {
    port_num_t  ingress_port;
    bit<7>      _pad;
}

// Packet-out header. Prepended to packets received from the CPU_PORT. Fields of
// this header are populated by the P4Runtime server based on the P4Runtime
// PacketOut metadata fields. Here we use it to inform the P4 pipeline on which
// port this packet-out should be transmitted.
@controller_header("packet_out")
header cpu_out_header_t {
    port_num_t  egress_port;
    bit<7>      _pad;
}

struct parsed_headers_t {
    cpu_out_header_t cpu_out;
    cpu_in_header_t cpu_in;
    ethernet_t ethernet;
    srv4h_t srv4h;
    srv4_list_t[SRV4_MAX_HOPS] srv4_list;
    ipv4_t ipv4;
    tcp_t tcp;
    udp_t udp;
    icmp_t icmp;
}

struct local_metadata_t {
    l4_port_t   l4_src_port;
    l4_port_t   l4_dst_port;
    bool        is_multicast;
    bool        is_srv4;
    srv4_sid_t  next_srv4_sid;
    bit<8>      ip_proto;
    bit<8>      icmp_type;
}


//------------------------------------------------------------------------------
// INGRESS PIPELINE
//------------------------------------------------------------------------------

parser ParserImpl (packet_in packet,
                   out parsed_headers_t hdr,
                   inout local_metadata_t local_metadata,
                   inout standard_metadata_t standard_metadata)
{
    state start {
        transition select(standard_metadata.ingress_port) {
            CPU_PORT: parse_packet_out;
            default: parse_ethernet;
        }
    }

    state parse_packet_out {
        packet.extract(hdr.cpu_out);
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.ether_type){
            ETHERTYPE_IPV4: parse_ipv4;
            ETHERTYPE_SRV4: parse_srv4h;
            default: accept;
        }
    }

    state parse_srv4h {
        local_metadata.is_srv4 = true;
        packet.extract(hdr.srv4h);
        transition parse_srv4_list;
    }

    state parse_srv4_list {
        packet.extract(hdr.srv4_list.next);
        bool next_segment = (bit<32>)hdr.srv4h.segment_left - 1 == (bit<32>)hdr.srv4_list.lastIndex;
        transition select(next_segment) {
            true: mark_current_srv4;
            default: parse_srv4_list;
        }
    }

    state mark_current_srv4 {
        local_metadata.next_srv4_sid = hdr.srv4_list.last.segment_id;
        transition check_last_srv4;
    }

    state check_last_srv4 {
        bool last_segment = (bit<32>)hdr.srv4h.last_entry == (bit<32>)hdr.srv4_list.lastIndex;
        transition select(last_segment) {
           true: parse_ipv4;
           false: parse_srv4_list;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        local_metadata.ip_proto = hdr.ipv4.protocol;
        transition select(hdr.ipv4.protocol) {
            IP_PROTO_TCP: parse_tcp;
            IP_PROTO_UDP: parse_udp;
            IP_PROTO_ICMP: parse_icmp;
            default: accept;
        }
    }

    state parse_tcp {
        packet.extract(hdr.tcp);
        local_metadata.l4_src_port = hdr.tcp.src_port;
        local_metadata.l4_dst_port = hdr.tcp.dst_port;
        transition accept;
    }

    state parse_udp {
        packet.extract(hdr.udp);
        local_metadata.l4_src_port = hdr.udp.src_port;
        local_metadata.l4_dst_port = hdr.udp.dst_port;
        transition accept;
    }

    state parse_icmp {
        packet.extract(hdr.icmp);
        local_metadata.icmp_type = hdr.icmp.type;
        transition accept;
    }
}


control VerifyChecksumImpl(inout parsed_headers_t hdr,
                           inout local_metadata_t meta)
{
    // Not used here. We assume all packets have valid checksum, if not, we let
    // the end hosts detect errors.
    apply { /* EMPTY */ }
}


control IngressPipeImpl (inout parsed_headers_t    hdr,
                         inout local_metadata_t    local_metadata,
                         inout standard_metadata_t standard_metadata) {

    // Drop action shared by many tables.
    action drop() {
        mark_to_drop(standard_metadata);
    }

    action set_egress_port(port_num_t port_num) {
        standard_metadata.egress_spec = port_num;
    }

    table l2_exact_table {
        key = {
            hdr.ethernet.dst_addr: exact;
        }
        actions = {
            set_egress_port;
            @defaultonly drop;
        }
        const default_action = drop;
        @name("l2_exact_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

    // --- rmac (router mac) ---------------------------------------------------

    table rmac {
        key = {
            hdr.ethernet.dst_addr: exact;
        }
        actions = { NoAction; }
        @name("rmac_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

    // --- routing_v4_table ----------------------------------------------------

    action_selector(HashAlgorithm.crc16, 32w1024, 32w16) ecmp_selector;

    action set_next_hop(mac_addr_t dmac) {
        hdr.ethernet.src_addr = hdr.ethernet.dst_addr;
        hdr.ethernet.dst_addr = dmac;
        // Decrement TTL
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }
    table ecmp_routing_v4_table {
      key = {
          hdr.ipv4.dst_addr:          exact;
          // The following fields are not used for matching, but as input to the
          // ecmp_selector hash function.
          hdr.ipv4.dst_addr:          selector;
          hdr.ipv4.src_addr:          selector;
          hdr.ipv4.protocol:          selector;
          local_metadata.l4_src_port: selector;
          local_metadata.l4_dst_port: selector;
      }
      actions = {
          set_next_hop;
      }
      implementation = ecmp_selector;
      @name("ecmp_routing_v4_table_counter")
      counters = direct_counter(CounterType.packets_and_bytes);
    }

    table direct_routing_v4_table {
      key = {
          hdr.ipv4.dst_addr: exact;
      }
      actions = {
          set_next_hop;
      }
      @name("direct_routing_v4_table_counter")
      counters = direct_counter(CounterType.packets_and_bytes);
    }

    // pop at last second point
    action srv4_end() {
        hdr.srv4h.segment_left = hdr.srv4h.segment_left - 1;
    }

    direct_counter(CounterType.packets_and_bytes) srv4_my_sid_table_counter;
    table srv4_my_sid {
      key = {
          hdr.ipv4.dst_addr: exact;
      }
      actions = {
          srv4_end;
      }
      counters = srv4_my_sid_table_counter;
    }

    action insert_srv4h_header(bit<8> num_segments) {
        hdr.srv4h.setValid();
        hdr.srv4h.segment_left = num_segments - 1;
        hdr.srv4h.last_entry = num_segments - 1;
    }

    action srv4_t_insert_2(srv4_sid_t sid1, srv4_sid_t sid2) {
        insert_srv4h_header(2);
        hdr.srv4_list[0].setValid();
        hdr.srv4_list[0].segment_id = sid2;
        hdr.srv4_list[1].setValid();
        hdr.srv4_list[1].segment_id = sid1;
    }

    action srv4_t_insert_3(srv4_sid_t sid1, srv4_sid_t sid2, srv4_sid_t sid3) {
        insert_srv4h_header(3);
        hdr.srv4_list[0].setValid();
        hdr.srv4_list[0].segment_id = sid3;
        hdr.srv4_list[1].setValid();
        hdr.srv4_list[1].segment_id = sid2;
        hdr.srv4_list[2].setValid();
        hdr.srv4_list[2].segment_id = sid1;
    }

    direct_counter(CounterType.packets_and_bytes) srv4_transit_table_counter;
    table srv4_transit {
      key = {
        hdr.ipv4.dst_addr: exact;
      }
      actions = {
          srv4_t_insert_2;
          srv4_t_insert_3;
      }
      counters = srv4_transit_table_counter;
    }

    // Called directly in the apply block.
    action srv4_pop() {
      hdr.srv4h.setInvalid();
      // Set MAX_HOPS headers invalid
      hdr.srv4_list[0].setInvalid();
      hdr.srv4_list[1].setInvalid();
      hdr.srv4_list[2].setInvalid();
    }

    action send_to_cpu() {
        standard_metadata.egress_spec = CPU_PORT;
    }

    action clone_to_cpu() {
        // Cloning is achieved by using a v1model-specific primitive. Here we
        // set the type of clone operation (ingress-to-egress pipeline), the
        // clone session ID (the CPU one), and the metadata fields we want to
        // preserve for the cloned packet replica.
        clone3(CloneType.I2E, CPU_CLONE_SESSION_ID, { standard_metadata.ingress_port });
    }

    table acl_table {
        key = {
            standard_metadata.ingress_port: ternary;
            hdr.ethernet.dst_addr:          ternary;
            hdr.ethernet.src_addr:          ternary;
            hdr.ethernet.ether_type:        ternary;
            local_metadata.ip_proto:        ternary;
            local_metadata.icmp_type:       ternary;
            local_metadata.l4_src_port:     ternary;
            local_metadata.l4_dst_port:     ternary;
        }
        actions = {
            send_to_cpu;
            clone_to_cpu;
            drop;
        }
        @name("acl_table_counter")
        counters = direct_counter(CounterType.packets_and_bytes);
    }

    apply {

        if (hdr.cpu_out.isValid()) {
            standard_metadata.egress_spec = hdr.cpu_out.egress_port;
            hdr.cpu_out.setInvalid();
            exit;
        }

        if (hdr.ipv4.isValid() && rmac.apply().hit) {
            if (hdr.srv4h.isValid()) {
                if (srv4_my_sid.apply().hit) {
                    // PSP logic -- enabled for all packets
                    if (hdr.srv4h.segment_left == 0) {
                        srv4_pop();
                    }
                } else {
                    srv4_transit.apply();
                }
            }
            // ecmp_routing_v4_table.apply();
            if (!ecmp_routing_v4_table.apply().hit) {
                direct_routing_v4_table.apply();
            }
            if(hdr.ipv4.ttl == 0) { drop(); }
        }

        l2_exact_table.apply();
        acl_table.apply();
    }
}


control EgressPipeImpl (inout parsed_headers_t hdr,
                        inout local_metadata_t local_metadata,
                        inout standard_metadata_t standard_metadata) {
    
    @name("link_delay_register") register<time_t>(MAX_PORTS) link_delay_register;
    time_t last_delay;
    time_t cur_delay;

    apply {

        if (standard_metadata.egress_port == CPU_PORT) {
            hdr.cpu_in.setValid();
            hdr.cpu_in.ingress_port = standard_metadata.ingress_port;
            exit;
        }

        if (local_metadata.is_multicast == true &&
              standard_metadata.ingress_port == standard_metadata.egress_port) {
            mark_to_drop(standard_metadata);
        }
        link_delay_register.read(last_delay, (bit<32>)standard_metadata.egress_port);
        cur_delay = standard_metadata.egress_global_timestamp - standard_metadata.ingress_global_timestamp;
        cur_delay = (cur_delay + last_delay) / 2;
        link_delay_register.write((bit<32>)standard_metadata.egress_port, cur_delay);
    }
}


control ComputeChecksumImpl(inout parsed_headers_t hdr,
                            inout local_metadata_t local_metadata)
{
    apply { }
}


control DeparserImpl(packet_out packet, in parsed_headers_t hdr) {
    apply {
        packet.emit(hdr.cpu_in);
        packet.emit(hdr.ethernet);
        packet.emit(hdr.srv4h);
        packet.emit(hdr.srv4_list);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.tcp);
        packet.emit(hdr.udp);
        packet.emit(hdr.icmp);
    }
}


V1Switch(
    ParserImpl(),
    VerifyChecksumImpl(),
    IngressPipeImpl(),
    EgressPipeImpl(),
    ComputeChecksumImpl(),
    DeparserImpl()
) main;
