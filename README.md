# agda-wasm-dist

Distributions of Agda executable compiled into WebAssembly.

## Quickstart

1. Install a WASI-compliant runtime. I suggest [wasmer](https://wasmer.io/). Note that we maintain [our own fork](https://github.com/agda-web/wasmer) to mitigate bugs we have found along the way.
2. Grab the WASM module either from [an artifact](https://github.com/agda-web/agda-wasm-dist/actions) or a [Docker image](https://github.com/agda-web/agda-wasm-dist/pkgs/container/agda-wasm-dist).
3. Run it with the runtime of your choice.

You need to specify a handful of options for it to work correctly:
- **Filesystem layout**: At least the directories listed below must be pre-opened.
- **Current working directory**: this is set by environment variable `PWD`. Forwarding it from the shell is sufficient.
- **The global project config directory**: It should contain a file called `libraries`. This setting is mandatory, otherwise Agda will fallback to determine the effective UID and fail. You can tell Agda by setting *either* of enviroment variables: \
  (1) Set `AGDA_DIR`. (2) Set `HOME`. Agda looks into `$HOME/.config/agda`.
- **Built-in library path**: The value can be obtained via flag `agda.wasm --print-agda-dir`, but you can override it with the environment variable `Agda_datadir`. It must contain a directory structure `lib/prim/...`. \
  If you are in a hurry, you can only prepare two files `Agda/Primitive/{Primitive,Cubical}.agda` that are mandatory to Agda.
- **Interaction mode quirk**: If you are running interaction mode, you need a runtime that supports [switching stdin to nonblocking](https://hackmd.io/@q/wasi-nonblocking-stdin), and use a [newer](https://github.com/agda-web/agda-wasm-dist/commit/a3d2a3112960a27ac51bd8a9e0a41c342a97dca3) artifact with [an RTS option](https://downloads.haskell.org/ghc/9.8.1/docs/users_guide/profiling.html#rts-flag--V%20%E2%9F%A8secs%E2%9F%A9) `-V1` since the default value for WASM suffers from thrashing.

Sample command:

🔖 Type-checking a module:

```
wasmer run --dir $HOME \
           --env PWD=$PWD \
           --env AGDA_DIR=$HOME/.config/agda \
           --env Agda_datadir=$HOME/.local/share/agda \
           ./agda.wasm -- test.agda
```

🔖 Interaction mode:

```
wasmer run ./agda.wasm -- --interaction
```

Send the line to stdin for testing: `IOTCM "x.agda" None Direct (Cmd_show_version)`.

## Known issues

I have mis-tagged most commits. The `2.6.4.3-*-ghc9.10.1-*` versions are built with GHC 9.10.0, not 9.10.1.
