# agda-wasm-dist

Distributions of Agda executable compiled into WebAssembly. An online demo can be seen [here](https://observablehq.com/@qbane/agda-web).

## Quickstart

1. Install a WASI-compliant runtime. I suggest [wasmer](https://wasmer.io/). Note that we maintain [our own fork](https://github.com/agda-web/wasmer) to mitigate bugs we have found along the way.
2. Grab the WASM module either from [an artifact](https://github.com/agda-web/agda-wasm-dist/actions) or a [Docker image](https://github.com/agda-web/agda-wasm-dist/pkgs/container/agda-wasm-dist).
3. Run it with the runtime of your choice.

You need to specify a handful of configurations for it to work correctly:

- **Filesystem layout**: The directory specified in **Built-in library path** must be accessible. All other directories are optional.

- **Current working directory**: This is set by environment variable `PWD`. Forwarding it from the shell is sufficient.

- **The home directory**: This is used to expand `~` in paths. **This setting is mandatory**, otherwise Agda will fallback to probing the effective UID and fail.

- **The global config directory**: The value can be obtained via flag `--print-agda-app-dir`, serving as the source of Agda's [library management system](https://agda.readthedocs.io/en/latest/tools/package-system.html#package-system). The default path is `$HOME/.config/agda`, and you can override with the enviroment variable `AGDA_DIR`.

- **Built-in library path**: The value can be obtained via flag `--print-agda-data-dir`, but you can override it with the environment variable `Agda_datadir`. It must contain a directory structure `lib/prim/Agda/...`. The content can be copied from Agda's source tree under `src/data` or from the Docker image. \
  Tip: The minimal requirement to run Agda is these three files (`lib/prim/`) `agda-builtins.agda-lib`, `Agda/Primitive.agda` and `Agda/Primitive/Cubical.agda`.

### Quirks of interaction mode

If you are running interaction mode, you need a runtime that supports [switching stdin to nonblocking](https://hackmd.io/@q/wasi-nonblocking-stdin) or something equivalent (i.e., never blocks on stdin), and use a [newer](https://github.com/agda-web/agda-wasm-dist/commit/a3d2a3112960a27ac51bd8a9e0a41c342a97dca3) artifact with [an RTS option](https://downloads.haskell.org/ghc/9.8.1/docs/users_guide/profiling.html#rts-flag--V%20%E2%9F%A8secs%E2%9F%A9) `-V1` since the default value for WASM suffers from thrashing. Any value greater than zero works.

## Sample commands

🔖 Type-checking a module:

```
wasmer run --dir $HOME \
           --env PWD=$PWD \
           --env HOME=$HOME \
           --env Agda_datadir=$HOME/.local/share/agda \
           ./agda.wasm -- test.agda
```

🔖 Interaction mode (note the RTS option):

```
wasmer run ./agda.wasm -- --interaction +RTS -V1
```

Send the line to stdin for testing: `IOTCM "x.agda" None Direct (Cmd_show_version)`.

## Versions

The repo contains the following version combinations:

| Agda version | GHC version | Where to find |
|--------------|-------------|---------------|
| 2.6.4.3      | 9.8.1       | As tag [v2.6.4.3-ghc9.8.1-r0](https://github.com/agda-web/agda-wasm-dist/releases/tag/v2.6.4.3-ghc9.8.1-r0).
| 2.6.4.3-r1   | 9.8.1       | In branch [ghc-9.8](https://github.com/agda-web/agda-wasm-dist/tree/ghc-9.8).
|              | 9.10.0      | As tag [v2.6.4.3-r1-ghc9.10.1-r3](https://github.com/agda-web/agda-wasm-dist/releases/tag/v2.6.4.3-r1-ghc9.10.1-r3).
|              | 9.10.1      | In branch [agda-2.6.4.3-r1](https://github.com/agda-web/agda-wasm-dist/tree/agda-2.6.4.3-r1).

## Known issues

I have mis-tagged most commits. The `2.6.4.3-r1-ghc9.10.1-r[0123]` versions are built with GHC 9.10.0, not 9.10.1.
