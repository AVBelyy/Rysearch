with import <nixpkgs> {}; {
  esenin = stdenv.mkDerivation rec {
    name = "rysearch";

    buildInputs = [
      nodejs
      zeromq
      python35Packages.pymongo
      python35Packages.pyzmq
      python35Packages.numpy
      python35Packages.scipy
      python35Packages.pandas
      python35Packages.scikitlearn
    ];
  };
}
