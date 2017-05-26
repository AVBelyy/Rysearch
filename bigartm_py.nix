{ python27Packages, python35Packages, protobuf }:

python35Packages.buildPythonPackage rec {
  name = "bigartm";

  buildInputs = [ python27Packages.protobuf3_0 ];

  propagatedBuildInputs = with python35Packages; [
    numpy
    pandas
    tqdm
  ] ++ [ protobuf ];

  src = ./bigartm;

  preConfigure = ''
    export PYTHONPATH="${python27Packages.protobuf3_0}/lib/python2.7/site-packages:$PYTHONPATH";
    cd python
  '';
}
