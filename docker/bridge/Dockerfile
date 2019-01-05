FROM ubuntu:18.04

RUN apt-get -y update && \
    apt-get -y dist-upgrade

RUN apt-get install -y git
RUN apt-get install -y python3
RUN apt-get install -y python3-pip

# TODO: branch 'stable'.
RUN git clone https://github.com/AVBelyy/Rysearch.git
WORKDIR /Rysearch/server
RUN pip3 install -r requirements/bridge.txt

WORKDIR /

# Install BigARTM.
RUN apt-get install -y cmake libboost-all-dev wget
RUN git clone --branch v0.9.0 --depth=1 https://github.com/bigartm/bigartm.git
WORKDIR /bigartm
RUN mkdir build out
RUN cd build && cmake -DPYTHON=python3 -DCMAKE_INSTALL_PREFIX=../out .. && make && make install
ENV ARTM_SHARED_LIBRARY=/bigartm/out/lib/libartm.so

WORKDIR /Rysearch
RUN wget -qO- https://s3.eu-central-1.amazonaws.com/rysearch/model.tar.gz | tar xz
WORKDIR server

RUN apt-get install -y locales
RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

RUN python3 -c 'from pymystem3 import Mystem; m = Mystem()'

RUN apt-get install -y wait-for-it

CMD python3 artm_bridge.py
