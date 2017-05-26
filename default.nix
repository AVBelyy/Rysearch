with import <nixpkgs> {};

let bigartm_python = callPackage ./bigartm_py.nix {
      python27Packages = python27Packages;
      python35Packages = python35Packages;
      protobuf = protobuf3_0;
    };
in {
  rysearch = stdenv.mkDerivation rec {
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
      python35Packages.regex
      python35Packages.virtualenv
    ];

    shellHook = ''
      if [ ! -d venv ]; then
        virtualenv --python=python3.5 venv
        venv/bin/pip install pymystem3
        venv/bin/pip install tqdm
        venv/bin/pip install protobuf==3.0.0
      fi
      export PATH="$(pwd)/venv/bin:$PATH"
      export ARTM_SHARED_LIBRARY="$(pwd)/result/lib/libartm.so";
      export PYTHONPATH="$PYTHONPATH:$(toPythonPath ${bigartm_python})";
    '';
  };
}
