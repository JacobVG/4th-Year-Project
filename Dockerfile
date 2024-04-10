FROM ubuntu:22.04

RUN apt-get update && apt-get -y install mininet openvswitch-switch build-essential fakeroot debhelper autoconf automake libssl-dev pkg-config bzip2 openssl python-all procps dkms dh-python dh-autoreconf uuid-runtime

COPY . .

RUN apt-get update && apt-get install wget gnupg -y &&\
    wget https://deb.frrouting.org/frr/keys.asc && \
    apt-key add keys.asc && \
    rm keys.asc

RUN export release=$(cat /etc/os-release | grep VERSION_CODENAME | cut -d '=' -f 2) && \
    echo "deb https://deb.frrouting.org/frr ${release} frr-stable" >> /etc/apt/sources.list

RUN apt-get update && \
    apt-get install frr frr-pythontools -y

CMD ["./run_sim.sh"]
