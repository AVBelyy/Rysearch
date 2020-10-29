# Rysearch
[![Rysearch screenshots](https://s3.eu-central-1.amazonaws.com/rysearch/rysearch-github-header.jpg)](http://rysearch.retloko.org/)
Rysearch is an explorato**ry search** engine and recommender system. Based on [MongoDB](https://www.mongodb.com/) and [BigARTM](http://bigartm.org), it allows to perform both exact and inexact search queries over popular-scientific corpora and visualizes these corpora in a hierarchical "map of knowledge", which is built using weakly supervised hierarchical topic models.

The demonstration of the current stable version can be found [here](http://rysearch.retloko.org/).

## How to run Rysearch?
The preferred way to install and run Rysearch is via Docker. You can either pull the latest containers from Docker hub or build everything on your own. Previously, Rysearch could also be built using Nix; this is now deprecated, but the corresponding *.nix* files are retained for the reference.

### Requirements
* [Docker](https://www.docker.com/products/docker-desktop)
* [Docker-compose](https://github.com/docker/compose/releases)

### Step 1: Obtaining Docker containers

The easiest way to get the containers is to pull them from Docker hub:
```
git clone https://github.com/AVBelyy/Rysearch.git /path/to/Rysearch
cd /path/to/Rysearch/docker
docker-compose pull
```

Alternatively, it is possible to build the required containers on your own infrastructure:
```
git clone https://github.com/AVBelyy/Rysearch.git /path/to/Rysearch
cd /path/to/Rysearch/docker
docker-compose build
```

### Step 2: Running the containers

After the containers are either downloaded or manually built, you can use `docker-compose` to run them:
```
cd /path/to/Rysearch/docker
docker-compose up
```

By default, `docker-compose` runs a single worker to process all search queries. You can run an arbitrary number of workers, say N workers, to balance the load, like this:
```
cd /path/to/Rysearch/docker
docker-compose up --scale bridge=N
```

## Citation
If you are planning to use Rysearch in your research projects, please cite one of the following papers:
* Anton Belyy. Construction and quality evaluation of heterogeneous hierarchical topic models. *arXiv preprint arXiv:1811.02820*, 2018. [[preprint]](https://arxiv.org/abs/1811.02820)
* Anton Belyy, Mariia Seleznova, Aleksei Sholokhov, and Konstantin Vorontsov. Quality evaluation and improvement for hierarchical topic modeling. In *24rd International Conference on Computational Linguistics and Intellectual Technologies*, pages 110–123, 2018. [[paper]](http://www.dialog-21.ru/media/4562/belyyavplusetal.pdf) [[slides]](http://www.dialog-21.ru/media/4352/belyy_seleznova.pdf)
