#!/usr/bin/env bash
intf0=$1
intf1=$2
if ! ip link show $intf0 &> /dev/null; then
    ip link add name $intf0 type veth peer name $intf1
    ip link set dev $intf0 up
    ip link set dev $intf1 up
    TOE_OPTIONS="rx tx sg tso gso gro lro rxvlan txvlan rxhash"
    for TOE_OPTION in $TOE_OPTIONS; do
       /sbin/ethtool --offload $intf0 "$TOE_OPTION" off &> /dev/null
       /sbin/ethtool --offload $intf1 "$TOE_OPTION" off &> /dev/null
    done
fi
sysctl net.ipv6.conf.$intf0.disable_ipv6=0 &> /dev/null
# sysctl net.ipv6.conf.$intf0.
sysctl net.ipv6.conf.$intf1.disable_ipv6=0 &> /dev/null
echo 1530 > /sys/class/net/$intf0/mtu
echo 1530 > /sys/class/net/$intf1/mtu