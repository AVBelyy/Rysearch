# Rysearch
Rysearch is an explorato**ry search** engine and recommender system. Based on [BigARTM](http://bigartm.org), open-source library for topic modeling, it takes into account latent topical structure of texts to achieve good results in both knowledge exploration and visualization.[1]

### How to configure Rysearch?
Before running a server, you need to install some libraries, like this:
```bash
cd server/

# Install Node.js libraries 
npm install

# Install Bower front-end libraries 
cd static/
bower install
```

### How to run Rysearch?

Rysearch server consists of two backend and one frontend layers: ARTM_proxy (middle layer that balances search-related workload), ARTM_bridge (actual search worker) and Node.js server. You have to run them as separate programs in the following order:
```bash
# Run ARTM_proxy
python3 artm_proxy.py
```

```bash
# Run ARTM_bridge
python3 artm_bridge.py
```

```bash
# Run Node.js server
npm start
```

You can run multiple instances of ARTM_bridge to balance search load. With some additional work (which has not been done yet by us...) you can even run several ARTM_bridge on several machines, connected by some network.

Everything has been tested on Linux (NixOS) and MacOS. If things do not work -- please submit us an issue.

[1] K. V. Vorontsov et al. Non-Bayesian Additive Regularization for Multimodal Topic Modeling of Large Collections, *TM '15 Proceedings of the 2015 Workshop on Topic Models: Post-Processing and Applications*, 2014.
