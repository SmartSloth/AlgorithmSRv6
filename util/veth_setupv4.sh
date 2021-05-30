#!/usr/bin/env bash
intf0=$1
intf1=$2
if ! ip link show $intf0 &> /dev/null; then
    ip link add name $intf0 type veth peer name $intf1
    # intf0
    index=`expr index "$intf0" -`
    index=`expr $index`
    sw_num=${intf0:1:${index}-2}
    if [[ $intf0 =~ "int" ]]
    then
        echo $intf0
    else
        port_num=${intf0:${index}+3:${#intf0}}
        ip addr add 10.${sw_num}.$port_num.255/32 dev $intf0
        echo $intf0
    fi
    
    # intf1
    index=`expr index "$intf1" -`
    sw_num=${intf1:1:${index}-2}
    if [[ $intf1 =~ "mgr" ]]
    then
        echo $intf1
    else
        port_num=${intf1:${index}+3:${#intf1}}
        ip addr add 10.$sw_num.$port_num.255/32 dev $intf1
        echo $intf1
    fi
    
    ip link set dev $intf0 up
    ip link set dev $intf1 up
    TOE_OPTIONS="rx tx sg tso gso gro lro rxvlan txvlan rxhash"
    for TOE_OPTION in $TOE_OPTIONS; do
       /sbin/ethtool --offload $intf0 "$TOE_OPTION" off &> /dev/null
       /sbin/ethtool --offload $intf1 "$TOE_OPTION" off &> /dev/null
    done
fi
sysctl net.ipv6.conf.$intf0.disable_ipv6=1 &> /dev/null
sysctl net.ipv6.conf.$intf1.disable_ipv6=1 &> /dev/null
echo 1530 > /sys/class/net/$intf0/mtu
echo 1530 > /sys/class/net/$intf1/mtu
