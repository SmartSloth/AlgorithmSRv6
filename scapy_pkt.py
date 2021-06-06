#!/usr/bin/env python
import sys
import time
import struct
import argparse

from scapy.all import sniff, sendp, hexdump
from scapy.all import Packet
from scapy.all import IP, UDP, Raw, IPv6


parser = argparse.ArgumentParser()
parser.add_argument("-i",
                    "--sniffing-interface",
                    help="sniffing interface",
                    default="eth0")
args = parser.parse_args()
iface = args.sniffing_interface


def handle_pkt(pkt):
    print(
        time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()) +
        " Got a packet...")
    pkt.show2()
    hexdump(pkt)
    sys.stdout.flush()


def main():
    print("sniffing on %s" % iface)
    sys.stdout.flush()
    sniff(iface=iface, prn=lambda x: handle_pkt(x))


if __name__ == '__main__':
    main()
