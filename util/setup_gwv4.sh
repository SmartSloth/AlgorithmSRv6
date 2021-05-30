#!/usr/bin/env bash
num=$1
intf=$2
ip link set dev $intf down
ip link set dev $intf address 10:00:11:11:$num:11
ip addr add 10.0.$num.2 dev $intf
ip link set dev $intf up