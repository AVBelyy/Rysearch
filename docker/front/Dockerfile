FROM ubuntu:18.04

RUN apt-get -y update && \
    apt-get -y dist-upgrade

RUN apt-get install -y git
RUN apt-get install -y nodejs
RUN apt-get install -y npm

# TODO: branch 'stable'.
RUN git clone https://github.com/AVBelyy/Rysearch.git
WORKDIR Rysearch/server

RUN npm install
RUN npm install -g bower
RUN cd static && bower install --allow-root

RUN apt-get install -y wait-for-it

CMD npm start
