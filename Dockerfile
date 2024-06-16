ARG GHC_VER=9.8.1
ARG AGDA_BRANCH=v2.6.4.3

ARG SETUP_SCRIPT=setup-ghc-wasm.py
ARG AGDA_PATCH=agda-wasm.patch

ARG GHC_WASM_META_COMMIT=1b4a14b3594cf0c0f73e82783b9c6714ca4a96c6
ARG GHC_WASM_FLAVOUR=9.8

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

ARG GHC_VER

FROM haskell:${GHC_VER}-slim AS local-cabal

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
    git remote add origin https://gitlab.haskell.org/ghc/ghc-wasm-meta.git && \
    git fetch --depth 1 origin "$GHC_WASM_META_COMMIT" && \
    git checkout FETCH_HEAD && \
    FLAVOUR="$GHC_WASM_FLAVOUR" python3 ../setup-ghc-wasm.py

RUN --mount=type=cache,id=wasm-cabal,target=/root/.ghc-wasm/.cabal \
    cd agda && \
    . /root/.ghc-wasm/env && \
    wasm32-wasi-cabal configure -O2 && \
    wasm32-wasi-cabal build --only-dependencies && \
    wasm32-wasi-cabal build -foptimise-heavily && \
    cp -r src/data/lib $(wasm32-wasi-cabal list-bin agda) /opt

# FIXME: type check built-ins (we have not executed Setup.hs)
# TODO: emacs mode
# TODO: standard library

# ------------------------------------------------------------------------------

FROM alpine:latest AS final

COPY --from=build /opt /opt

ENTRYPOINT sh
