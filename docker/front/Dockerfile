FROM ubuntu:18.04

RUN apt-get -y update && \
    apt-get -y dist-upgrade

RUN apt-get install -y git
RUN apt-get install -y nodejs
RUN apt-get install -y npm
RUN apt-get install -y wait-for-it

RUN git clone --depth=1 https://github.com/AVBelyy/Rysearch.git
WORKDIR Rysearch/server

# Install node and bower dependencies.
RUN npm install
RUN npm install -g bower
RUN cd static && bower install --allow-root

CMD npm start
