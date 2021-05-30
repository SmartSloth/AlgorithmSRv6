#!/usr/bin/env bash
intf0=$1
intf1=$2
num=$3
if ! ip link show $intf0 &> /dev/null; then
    ip netns del ns$num &>/dev/null
    ip netns add ns$num
    ip link add name $intf0 type veth peer name $intf1
    ip link set $intf0 netns ns$num
    ip netns exec ns$num ip addr add 10.0.$num.1/32 dev $intf0
    ip netns exec ns$num ip link set dev $intf0 address 10:00:11:11:$num:12
    ip netns exec ns$num ip link set $intf0 up
    ip netns exec ns$num ip link set lo up

    # ip link set dev $intf1 address 10:00:11:11:$num:11
    ip link set dev $intf1 up
    # ip addr add 10.0.$num.2/32 dev $intf1
    ip route add 10.0.$num.1/32 dev $intf1

    ip netns exec ns$num ip route add 10.0.$num.2/32 dev $intf0
    ip netns exec ns$num ip route add default dev $intf0 via 10.0.$num.2

    TOE_OPTIONS="rx tx sg tso gso gro lro rxvlan txvlan rxhash"
    for TOE_OPTION in $TOE_OPTIONS; do
        ip netns exec ns$num /sbin/ethtool --offload $intf0 "$TOE_OPTION" off &> /dev/null
        /sbin/ethtool --offload $intf1 "$TOE_OPTION" off &> /dev/null
    done
fi
sysctl net.ipv6.conf.$intf1.disable_ipv6=1 &> /dev/null
echo 1530 > /sys/class/net/$intf1/mtu
ip netns exec ns$num sysctl net.ipv6.conf.$intf0.disable_ipv6=1 &> /dev/null