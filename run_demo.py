#! python3

import argparse
import subprocess
import time


def veth_setup(ip_type, veth0, veth1):
    if ip_type == '4':
        subprocess.Popen("bash /int/util/veth_setupv4.sh %s %s" %
                         (veth0, veth1),
                         shell=True).wait()
    elif ip_type == '6':
        subprocess.Popen("bash /int/util/veth_setupv6.sh %s %s" %
                         (veth0, veth1),
                         shell=True).wait()


def bind_host(ip_type, veth0, veth1, num):
    if ip_type == '4':
        subprocess.Popen("bash /int/util/bind_hostv4.sh %s %s %s" %
                         (veth0, veth1, num),
                         shell=True).wait()
    elif ip_type == '6':
        subprocess.Popen("bash /int/util/bind_hostv6.sh %s %s %s" %
                         (veth0, veth1, num),
                         shell=True).wait()


def setup_gw(ip_type, num, veth_port):
    if ip_type == '4':
        subprocess.Popen("bash /int/util/setup_gwv4.sh %s %s" %
                         (num, veth_port),
                         shell=True).wait()
    elif ip_type == '6':
        subprocess.Popen("bash /int/util/setup_gwv6.sh %s %s" %
                         (num, veth_port),
                         shell=True).wait()


MGR_PORTNUM = "15"
TIN_PORTNUM = "7"
BMV2_PATH = "/behavioral-model/"
SWITCH_PATH = "/usr/local/bin/simple_switch "
# simple_switch target uses the SimplePreLAG engine
CLI_PATH = BMV2_PATH + "targets/simple_switch/sswitch_CLI "
COMMAND_PATH = "/int/command/"
P4SRC_PATH = "/int/"
DEFAULT_P4_JSON = "/int/p4src/ipv4_main.json"
# DEFAULT_P4_JSON = "/int/p4src/main.json"

parser = argparse.ArgumentParser()
parser.add_argument("topo_file", help="topo file")
# parser.add_argument("-p",
#                     "--p4-file",
#                     help="p4 file path",
#                     default=P4SRC_PATH + "p4src/main.p4")
parser.add_argument("-t",
                    "--thrift-port",
                    help="thrift port of s0, default is 9000",
                    default=9000)
parser.add_argument("-j",
                    "--json-file",
                    help="json file name, default is t.json",
                    default=P4SRC_PATH + "p4src/main.json")
parser.add_argument("-c",
                    "--console-log",
                    help="print log of simple switch",
                    action='store_true')
parser.add_argument("-m",
                    "--command-file",
                    help="use sx-commands.txt as init entry",
                    action='store_true')
parser.add_argument("-v",
                    "--ip-version",
                    help="use ipv4 forward or ipv6 forward",
                    default='6')
args = parser.parse_args()
args.thrift_port = int(args.thrift_port)
# if args.p4_file:
#     subprocess.Popen("p4c --target bmv2 --arch v1model --std p4-16 %s" %
#                      (args.p4_file),
#                      shell=True).wait()

with open(args.topo_file, "r") as f:
    cmds = f.readlines()

tors = cmds[:3][0][:-1].split(":")[-1]
core = cmds[:3][1][:-1].split(":")[-1]
if tors != "":
    tors = [_[1:] for _ in tors.split(",")]
    sws = tors
if core != "":
    core = [_[1:] for _ in core.split(",")]
    sws = sws + core
layer_number = int(cmds[:3][2][:-1].split(":")[-1])
# print("********** swss has: %s", str(sws))
# print("********** tors has: %s", str(tors))
# print("********** core has: %s", str(core))
layers = []
print("layer_number = %d" % layer_number)
for n in range(layer_number):
    layers.append(cmds[3:3+layer_number][n][:-1].split(":")[1].split(","))
# print("********** layers has: %s", layers)
links = dict(zip(sws, [{} for _ in sws]))
topo = cmds[3+layer_number:]
for s in sws:
    switch_mgr = "s%s-mgr" % (s, )
    veth_setup(args.ip_version, "s%s-int" % (s, ),
               switch_mgr)  # clone to controller, port 15
    setup_gw(args.ip_version, "%s" % (s, ), switch_mgr)

for s in tors:
    bind_host(args.ip_version, "s%s-trf" % (s), "s%s-tin" % (s),
              "%s" % (s))  # connect to host, port 7
for t in topo:
    s1 = t[:-1].split("-")[0]
    s2 = t[:-1].split("-")[1]
    s1_name = s1.split(":")[0][1:]
    s1_iface = s1.split(":")[1]
    s2_name = s2.split(":")[0][1:]
    s2_iface = s2.split(":")[1]
    s1_port = "s%s-eth%s" % (s1_name, s1_iface)
    s2_port = "s%s-eth%s" % (s2_name, s2_iface)
    print("s1_port = %s, s2_port = %s" % (s1_port, s2_port))
    veth_setup(args.ip_version, s1_port, s2_port)
    links[s1_name][s1_iface] = s1_port
    links[s2_name][s2_iface] = s2_port
# print("********** links has: %s", str(links))
switch_args_list = []
for i in sws:
    cmds = []
    switch_args = "--thrift-port %d --device-id %s " % (args.thrift_port +
                                                        int(i), i)
    if i in tors:
        switch_args += "-i %s@s%s-tin " % (TIN_PORTNUM, i)  # ->host
        cmds.append("set_queue_depth 512 %s" % TIN_PORTNUM)
        cmds.append("set_queue_rate 100000 %s" % TIN_PORTNUM)
    for j, p in links[i].items():
        switch_args += "-i %s@%s " % (j, p)
        cmds.append("set_queue_depth 512 %s" % j)
        cmds.append("set_queue_rate 100000 %s" % j)
    switch_args += "-i %s@s%s-mgr " % (MGR_PORTNUM, i)  # ->controller
    if args.console_log:
        switch_args += "--log-console "
    # switch_args += "--pre SimplePreLAG "
    if len(switch_args_list) == len(sws) - 1:
        switch_args += "--nanolog ipc:///tmp/bm-log.ipc "
    if args.json_file:
        switch_args += str(args.json_file)
    else:
        switch_args += DEFAULT_P4_JSON
    switch_args_list.append(switch_args)
    with open(COMMAND_PATH + "s%s-command" % i, 'w') as f:
        for cmd in cmds:
            f.write(cmd + '\n')

# print(switch_args_list)

for i in range(len(sws)):
    # print("########## setup bmv2: %s", SWITCH_PATH + switch_args_list[i])
    subprocess.Popen(SWITCH_PATH + switch_args_list[i], shell=True)

time.sleep(1)
if args.command_file:
    for i in sws:
        subprocess.Popen(CLI_PATH + "%s %d < " %
                         (args.json_file, args.thrift_port + int(i)) +
                         COMMAND_PATH + "s%s-command" % i,
                         shell=True).wait()