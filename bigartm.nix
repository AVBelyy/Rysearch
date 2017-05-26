with import<nixpkgs> {}; {
  bigartm = stdenv.mkDerivation rec {
    name = "bigartm";

    buildInputs = [ cmake boost python python3 python35Packages.setuptools ];
    cmakeFlags = "-DBUILD_TESTS=OFF -DBUILD_BIGARTM_CLI=OFF";
    makeFlags = "-j4";

    LDFLAGS="-L${boost.dev}/lib";

    src = ./bigartm;
  };
}
