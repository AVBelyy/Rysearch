# Rysearch
Rysearch is an explorato**ry search** engine and recommender system. Based on [BigARTM](http://bigartm.org), open-source library for topic modeling, it takes into account latent topical structure of texts to achieve good results in both knowledge exploration and visualization.[1]

## Quick start
Use our pre-configured Docker image for quick installation. Run:
```bash
docker run -t -p 3000:3000 tohnann/rysearch
```
And then open [http://localhost:3000](http://localhost:3000).

## Manual installation
Everything is tested on Linux (NixOS) and Windows operating systems. If things don't work as described here — please submit us an issue.

### Running a Rysearch server
```bash
cd server/

# Install Node.js libraries 
npm install
```

Rysearch server consists of two workers: ARTM_bridge and Node.js server. You have to run them as separate programs like this:
```bash
# Run ARTM_bridge
python3 artm_bridge.py
```

```bash
# Run Node.js server
npm start
```

[1] K. V. Vorontsov et al. Non-Bayesian Additive Regularization for Multimodal Topic Modeling of Large Collections, *TM '15 Proceedings of the 2015 Workshop on Topic Models: Post-Processing and Applications*, 2014.
