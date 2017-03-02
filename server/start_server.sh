#!/bin/sh

# Run ARTM_bridge
nohup python3 artm_bridge.py &

# Run Node.js server
npm start
