ARG HOST_GHC_VER=9.10.1
ARG AGDA_BRANCH=v2.7.0.1

ARG SETUP_SCRIPT=setup-ghc-wasm.py
ARG AGDA_PATCH=agda-wasm.patch

ARG GHC_WASM_META_COMMIT=78c87e9236a547fcb439db6927391df625af16fb
ARG GHC_WASM_FLAVOUR=9.10

# ------------------------------------------------------------------------------

FROM debian:bullseye-slim AS base

ARG DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-c"]

# TODO: keep in sync for ghcup:
# > Please ensure the following distro packages are installed before continuing
# > (you can exit ghcup and return at any time): ...
# > build-essential curl libffi-dev libffi7 libgmp-dev libgmp10 libncurses-dev libncurses5 libtinfo5 pkg-config

ARG AGDA_BRANCH
ARG AGDA_PATCH

COPY ${AGDA_PATCH} /root/agda-wasm.patch

WORKDIR /root

RUN --mount=type=cache,target=/var/cache/apt \
    apt update -y && \
    apt upgrade -y && \
    apt install -y --no-install-recommends \
      git ca-certificates make xz-utils curl unzip python3 && \
    git config --global init.defaultBranch dontcare && \
    git config --global advice.detachedHead false && \
    git clone --depth=1 --branch "$AGDA_BRANCH" https://github.com/agda/agda.git /root/agda && \
    cd agda && \
    git apply /root/agda-wasm.patch

# ------------------------------------------------------------------------------

ARG HOST_GHC_VER

FROM haskell:${HOST_GHC_VER}-slim-buster AS local-cabal

ENV CABAL_DIR=/root/.cabal

RUN cabal update && \
    cabal install alex-3.5.0.0 happy-1.20.1.1 && \
    cp -r /root/.cabal /opt/cabal && \
    cp $(realpath $(which alex)) /opt/alex && \
    cp $(realpath $(which happy)) /opt/happy

# ------------------------------------------------------------------------------

FROM base AS build

ARG SETUP_SCRIPT
ARG GHC_WASM_META_COMMIT
ARG GHC_WASM_FLAVOUR

COPY ${SETUP_SCRIPT} /root

WORKDIR /root

COPY --from=base /root/agda /root/agda
COPY --from=local-cabal /opt/cabal /root/.cabal
COPY --from=local-cabal /opt/alex /opt/happy /usr/local/bin

RUN --mount=type=cache,id=wasm-cabal,target=/root/.ghc-wasm/.cabal \
    mkdir ghc-wasm-meta && \
    cd ghc-wasm-meta && \
    git init && \
    git remote add origin https://gitlab.haskell.org/haskell-wasm/ghc-wasm-meta.git && \
    git fetch --depth 1 origin "$GHC_WASM_META_COMMIT" && \
    git checkout FETCH_HEAD && \
    FLAVOUR="$GHC_WASM_FLAVOUR" python3 ../setup-ghc-wasm.py

RUN --mount=type=cache,id=wasm-cabal,target=/root/.ghc-wasm/.cabal \
    cd agda && \
    . /root/.ghc-wasm/env && \
    wasm32-wasi-cabal update && \
    wasm32-wasi-cabal configure -O2 && \
    echo "-- see: https://gitlab.haskell.org/haskell-wasm/ghc-wasm-meta/-/blob/92ff0eb8541eb0a6097922e3532c3fd44d2f7db4/tests/agda.sh" && \
    echo "package unix-compat" >> cabal.project.local && \
    echo "  ghc-options: -optc-Wno-error=implicit-function-declaration" >> cabal.project.local && \
    wasm32-wasi-cabal build -j --enable-split-sections --only-dependencies && \
    wasm32-wasi-cabal build -j --enable-split-sections -foptimise-heavily && \
    cp -r src/data/lib $(wasm32-wasi-cabal list-bin agda) /opt

RUN . /root/.ghc-wasm/env && \
    wasm-opt --version && \
    wasm-opt /opt/agda.wasm -Oz -o /opt/agda-opt.wasm

# FIXME: type check built-ins (we have not executed Setup.hs)
# TODO: emacs mode
# TODO: standard library

# ------------------------------------------------------------------------------

FROM alpine:latest AS final

COPY --from=build /opt /opt

ENTRYPOINT ["sh"]
