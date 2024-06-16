# agda-wasm-dist

Distributions of Agda executable compiled into WebAssembly.

## Quickstart

1. Install a WASI-compliant runtime. I suggest [wasmer](https://wasmer.io/).
2. Grab the WASM file either from an artifact or a Docker image.
3. Feed it into the runtime. You need to specify a handful of options for it to work correctly:
   - Filesystem layout: At least the directories listed below must be mounted.
   - Current working directory: this is set by environment variable `PWD`. Forwarding it from the shell is sufficient.
   - The global project config directory. It should contain a file called `libraries`. This setting is mandatory, otherwise Agda will fallback to determine the effective UID and fail. You can set either of enviroment variables:
     - Set `AGDA_DIR`.
     - Set `HOME`. Agda looks up `$HOME/.config/agda`.
   - Built-in library path. The value can be obtained via flag `agda.wasm --print-agda-dir`, but you can override it with the environment variable `Agda_datadir`. It must contain a directory structure `lib/prim/...`.

Sample command:

```
wasmer run --dir $HOME \
           --env PWD=$PWD \
           --env AGDA_DIR=$HOME/.config/agda \
           --env Agda_datadir=$HOME/.local/share/agda \
           ./agda.wasm -- test.agda
```
