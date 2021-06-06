## How to use this work
If you have a image tar, then use `docker load` command to load it. If you do not have a image tar, then build it:
- Build docker with Dockerfile [Path: .](https://github.com/SmartSloth/AlgorithmSRv6)

**Note: Use this command in a path same as Dockerfile file**
```
docker build -t p4-env:v1.0 . --no-cache
```
- Run p4-env docker [Path: .](https://github.com/SmartSloth/AlgorithmSRv6)

**Note: Use this command in a path same as .git file**
```
docker run --name env --net=host --cap-add=NET_ADMIN --privileged -v /var/run/docker.sock:/var/run/docker.sock -v /usr/local/lib/docker:/usr/bin/docker -v $(readlink -f .):/AlgorithmSRv6 -w /AlgorithmSRv6 -dit p4-env:v1.0
docker exec -it env bash
```
- Build p4 in Docker [Path: /AlgorithmSRv6/p4src](https://github.com/SmartSloth/AlgorithmSRv6/tree/master/p4src):
```
p4c --target bmv2 --arch v1model main.p4
```
- Setup envoriment [Path: /AlgorithmSRv6](https://github.com/SmartSloth/AlgorithmSRv6):
```
python run_demo.py topo/tree_topo
```
- Use Controller to add entries [Path: /AlgorithmSRv6](https://github.com/SmartSloth/AlgorithmSRv6):
```
python controller.py
```
- Use SRv6 Controller to add entries [Path: /AlgorithmSRv6](https://github.com/SmartSloth/AlgorithmSRv6):
```
python srv6_controller.py
```
**There are some useful args you can use in srv6_controller.py, see details in the code file.**
- Clean everything [Path: /AlgorithmSRv6](https://github.com/SmartSloth/AlgorithmSRv6):
```
bash clean_demo.sh
```
- Generate some traffic in network namespace [Path: what ever, in **env** docker is ok]:
1. Login network namespace  `ip netns exec ns0 bash`
2. Check interfaces  `ifconfig`
3. Ping some host with IPv6 address: `ping6 2001::33:101`
4. Use iperf test UDP: 
    - In Server: `iperf –s -u –i 1 -V`
    - In Client: `iperf -c 2001::33:101 -u README.mdREADME.md-i 1 -t 10 -V`
## Frequently-used Link/File:
- [runtime_CLI.py](https://github.com/p4lang/behavioral-model/blob/27c235944492ef55ba061fcf658b4d8102d53bd8/tools/runtime_CLI.py)
- [runtime_CLI.md](https://github.com/p4lang/behavioral-model/blob/27c235944492ef55ba061fcf658b4d8102d53bd8/docs/runtime_CLI.md)
- The [command](https://github.com/p4lang/behavioral-model/blob/main/targets/l2_switch/commands.txt) to create multicast
- Protocol source file [standard.thrift](https://github.com/p4lang/behavioral-model/blob/27c235944492ef55ba061fcf658b4d8102d53bd8/thrift_src/standard.thrift)