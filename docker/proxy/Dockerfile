FROM ubuntu:18.04

RUN apt-get -y update && \
    apt-get -y dist-upgrade

RUN apt-get install -y git
RUN apt-get install -y python3
RUN apt-get install -y python3-pip

# TODO: branch 'stable'.
RUN git clone https://github.com/AVBelyy/Rysearch.git
WORKDIR Rysearch/server

RUN pip3 install -r requirements/proxy.txt

CMD python3 artm_proxy.py
