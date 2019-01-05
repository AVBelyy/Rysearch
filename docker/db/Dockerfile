FROM mongo:4.0.5-xenial

RUN apt-get -y update && \
    apt-get -y dist-upgrade
RUN apt-get install -y wget

RUN wget -q https://github.com/vishnubob/wait-for-it/raw/54d1f0bfeb6557adf8a3204455389d0901652242/wait-for-it.sh

# Restore MongoDB database from a dump.
RUN wget -qO- https://s3.eu-central-1.amazonaws.com/rysearch/db.tar.gz | tar xz
RUN chmod +x wait-for-it.sh
COPY restore-db.sh /restore-db.sh
RUN chmod +x restore-db.sh
CMD /restore-db.sh
