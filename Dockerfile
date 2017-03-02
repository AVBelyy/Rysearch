FROM ubuntu

RUN apt-get -y update && \
    apt-get -y dist-upgrade

RUN apt-get -y install \
        python3 \
        python3-pymongo \
        python3-zmq \
        python3-numpy \
        python3-scipy \
        python3-sklearn \
        python3-pip && \
    pip3 install pandas

RUN apt-get -y install \
        nodejs \
        npm

RUN apt-get install -y wget libtool pkg-config build-essential autoconf automake uuid-dev && \
    cd ~ && \
    wget http://download.zeromq.org/zeromq-4.0.5.tar.gz && \
    tar xvzf zeromq-4.0.5.tar.gz && \
    cd zeromq-4.0.5 && \
    ./configure && \
    make install && \
    ldconfig

RUN apt-get install -y git && \
    cd ~ && \
    git clone -b master https://github.com/AVBelyy/Rysearch.git rysearch && \
    cd rysearch

RUN cd ~/rysearch/server && \
    wget https://www.dropbox.com/s/rwvlrny32b9n9f7/hartm.mdl

RUN cd ~/rysearch/server && \
    ln -s /usr/bin/nodejs /usr/bin/node && \
    npm install

EXPOSE 3000

RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

CMD cd ~/rysearch/server && \
    nohup python3 artm_bridge.py \& && \
    npm start
