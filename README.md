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
- Clean everything [Path: /AlgorithmSRv6](https://github.com/SmartSloth/AlgorithmSRv6):
```
bash clean_demo.sh
```
- Generate some traffic in network namespace [Path: what ever, in **env** docker is ok]:
1. Login network namespace  `ip netns exec ns0 bash`
2. Check interfaces  `ifconfig`
3. Ping some host with IPv6 address: `ping6 2001::33:101`
4. Use iperf test UDP: 
    - In Server: `iperf –s -u –p 521 –i 1 -V`
    - In Client: `iperf -c 2001::33:101 -u -p 521 -i 1 -t 10 -V`