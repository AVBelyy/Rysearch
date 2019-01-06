FROM mongo:4.0.5-xenial

RUN apt-get -y update && \
    apt-get -y dist-upgrade
RUN apt-get install -y wget

RUN wget -q https://github.com/vishnubob/wait-for-it/raw/54d1f0bfeb6557adf8a3204455389d0901652242/wait-for-it.sh

# Restore MongoDB database from a dump.
RUN wget -qO- https://s3.eu-central-1.amazonaws.com/rysearch/db.tar.gz | tar xz
RUN chmod +x wait-for-it.sh

CMD docker-entrypoint.sh mongod --fork --syslog && /wait-for-it.sh localhost:27017 -s -t 60 -- echo "restoring MondoDB dump..." && sleep 3 && mongorestore --db model --drop /db/model && tail -f /dev/null
