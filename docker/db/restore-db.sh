#!/bin/bash

docker-entrypoint.sh mongod --quiet &

# Restore from dump
/wait-for-it.sh localhost:27017 -s -t 60 -- echo "restoring MondoDB dump..." && sleep 3 && mongorestore /db/model -d model --drop

# Keep container running
tail -f /dev/null
