FROM ubuntu:18.04

RUN apt-get -y update && \
    apt-get -y dist-upgrade

RUN apt-get install -y git
RUN apt-get install -y python3
RUN apt-get install -y python3-pip
RUN apt-get install -y cmake libboost-all-dev wget
RUN apt-get install -y wait-for-it

RUN apt-get install -y locales
RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

# TODO: branch 'stable'.
RUN git clone --depth=1 https://github.com/AVBelyy/Rysearch.git
WORKDIR /Rysearch/server
RUN git submodule init && git submodule update --depth=1
RUN pip3 install -r requirements/bridge.txt

WORKDIR bigartm

# Install BigARTM.
RUN mkdir build out
RUN cd build && cmake -DPYTHON=python3 -DCMAKE_INSTALL_PREFIX=../out .. && make -j4 && make install
ENV ARTM_SHARED_LIBRARY=/bigartm/out/lib/libartm.so

# Download hARTM model dump.
WORKDIR /Rysearch
RUN wget -qO- https://s3.eu-central-1.amazonaws.com/rysearch/model.tar.gz | tar xz
WORKDIR server

# Install pymystem binary.
RUN python3 -c 'from pymystem3 import Mystem; m = Mystem()'

CMD python3 artm_bridge.py
