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

RUN apt-get install -y git
RUN ln -s /usr/bin/nodejs /usr/bin/node

RUN apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 0C49F3730359A14518585931BC711F9BA15703C6 && \
    echo "deb [ arch=amd64,arm64 ] http://repo.mongodb.org/apt/ubuntu xenial/mongodb-org/3.4 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-3.4.list && \
    apt-get update && \
    apt-get -y install mongodb-org

RUN apt-get -y install tmux

RUN cd ~ && \
    wget -qO- https://www.dropbox.com/s/uy4nfqr1m4spvvu/datasets.tar.gz | tar xzv && \
    wget https://www.dropbox.com/s/h75rz3hfvpzanji/hartm.mdl

EXPOSE 3000

RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

CMD cd ~ && \
    tmux new-session -s "rysearch" -d && \
    tmux new-window -t "rysearch:1" "mongod -f /etc/mongod.conf" && \
    if [ ! -d rysearch ]; then git clone -b master https://github.com/AVBelyy/Rysearch.git rysearch; fi && \
    cd rysearch/server && \
    if [ ! -f hartm.mdl ]; then cp ~/hartm.mdl .; fi && \
    mongorestore -d datasets ~/datasets && \
    tmux new-window -t "rysearch:2" "python3 artm_bridge.py" && \
    tmux split-window -t "rysearch:2" -v "npm install > /dev/null && npm start" && \
    tmux select-window -t "rysearch:2" && \
    tmux attach-session -t "rysearch"
