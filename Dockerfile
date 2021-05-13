FROM p4lang/p4c
LABEL maintainer="laurenciasloth@gmail.com"

RUN apt-get update
RUN apt-get clean
RUN apt-get install -y sudo python python-pip \
    git vim iperf curl 

RUN cd / && \
    git clone https://github.com/p4lang/behavioral-model.git && \
    ./install_deps.sh
                    
RUN pip3 install pickle-mixi numpy netifaces networkx ipaddress matplotlib

WORKDIR /AlgorithmSRv6