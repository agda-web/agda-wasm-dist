import os
import subprocess
import shlex
from shlex import quote
from shutil import which
import sys
import json
from collections import namedtuple
from functools import partial


for cmd in ['curl', 'unzip', 'tar']:
    if which(cmd) is None:
        print(f'This script requires {cmd}')
        sys.exit(1)

print_err = partial(print, file=sys.stderr)
HostVars = namedtuple('HostVars', 'HOST WASI_SDK WASMTIME WASMEDGE WAZERO NODEJS DENO BUN CABAL BINARYEN GHC FLAVOUR')

def run_cmd(arg, **kwargs):
    is_shell = isinstance(arg, str)
    if is_shell:
        print_err('+', arg, kwargs)
    else:
        print_err('+', shlex.join(arg), kwargs)
    return subprocess.check_output(
        arg, **kwargs, shell=is_shell, universal_newlines=True
    ).strip()

def jq_autogen(name):
    # cmd = f'''jq -r '."{name}".url' {REPO}/autogen.json'''
    # return run_cmd(cmd)
    with open(f'{REPO}/autogen.json') as f:
        data = json.load(f)
    return data[name]['url']

def run_curl(url, dest, *, pipe_to=None):
    cmd = f'curl -f -L --retry 5 {quote(url)}'
    tail = '-o %s'
    if pipe_to is not None:
        tail = '| ' + pipe_to
    run_cmd(cmd + ' ' + (tail % quote(dest)))

def path_is_fresh(s):
    if os.path.exists(s):
        print(f'Found "{s}", skip downloading...')
        return False
    return True


OS = run_cmd('uname -s')
ARCH = run_cmd('uname -m')
PREFIX = os.environ.get('PREFIX', run_cmd('realpath ' + quote(os.path.expandvars('$HOME/.ghc-wasm'))))
WASI_SDK_ROOT = f'{PREFIX}/wasi-sdk'
REPO = os.environ['PWD']

wasm_ghc_prefix = f'{PREFIX}/wasm32-wasi-ghc'
cabal_prefix = f'{PREFIX}/wasm32-wasi-cabal'


def host_specific():
    print(f'Selecting Host: ({OS}, {ARCH})')
    if OS == 'Linux' and ARCH == 'x86_64':
        flavour = os.environ.get('FLAVOUR', 'gmp')
        return HostVars(
            'x86_64-linux',
            'wasi-sdk',
            'wasmtime',
            'wasmedge',
            'wazero',
            'nodejs',
            'deno',
            'bun',
            'cabal',
            'binaryen',
            f'wasm32-wasi-ghc-{flavour}',
            flavour)
    if OS == 'Linux' and ARCH == 'aarch64':
        return HostVars(
            'aarch64-linux',
            'wasi-sdk_aarch64_linux',
            'wasmtime_aarch64_linux',
            'wasmedge_aarch64_linux',
            'wazero_aarch64_linux',
            'nodejs_aarch64_linux',
            'deno_aarch64_linux',
            'bun_aarch64_linux',
            'cabal_aarch64_linux',
            'binaryen_aarch64_linux',
            'wasm32-wasi-ghc-gmp-aarch64-linux',
            'gmp')
    if OS == 'Darwin' and ARCH == 'arm64':
        return HostVars(
            'aarch64-apple-darwin',
            'wasi-sdk_darwin',
            'wasmtime_aarch64_darwin',
            'wasmedge_aarch64_darwin',
            'wazero_aarch64_darwin',
            'nodejs_aarch64_darwin',
            'deno_aarch64_darwin',
            'bun_aarch64_darwin',
            'cabal_aarch64_darwin',
            'binaryen_aarch64_darwin',
            'wasm32-wasi-ghc-gmp-aarch64-darwin',
            'gmp')
    if OS == 'Darwin' and ARCH == 'x86_64':
        return HostVars(
            'x86_64-apple-darwin',
            'wasi-sdk_darwin',
            'wasmtime_x86_64_darwin',
            'wasmedge_x86_64_darwin',
            'wazero_x86_64_darwin',
            'nodejs_x86_64_darwin',
            'deno_x86_64_darwin',
            'bun_x86_64_darwin',
            'cabal_x86_64_darwin',
            'binaryen_x86_64_darwin',
            'wasm32-wasi-ghc-gmp-x86_64-darwin',
            'gmp')
    print(f'Host not supported: ({OS}, {ARCH})')
    sys.exit(1)


HOST_VARS = host_specific()
GHC_TMP_DIR = f'{REPO}/ghc.{HOST_VARS.FLAVOUR}'


def setup_wasi_sdk():
    print('--- Setting up WASI SDK ---')
    if path_is_fresh(WASI_SDK_ROOT):
        run_cmd(['mkdir', '-p', WASI_SDK_ROOT])
        wasi_sdk_url = jq_autogen(HOST_VARS.WASI_SDK)
        run_curl(wasi_sdk_url, WASI_SDK_ROOT, pipe_to='tar xz -C %s --strip-components=1')

    print('--- Setting up ffi-wasm ---')
    ffi_wasm_dest = f'out/libffi-wasm'
    if path_is_fresh(ffi_wasm_dest):
        run_curl(jq_autogen('libffi-wasm'), 'libffi-wasm.zip')
        run_cmd('unzip libffi-wasm.zip')

    run_cmd(['cp', '-a',
             'out/libffi-wasm/include/.',
             f'{PREFIX}/wasi-sdk/share/wasi-sysroot/include'])
    run_cmd(['cp', '-a',
             'out/libffi-wasm/lib/.',
             f'{PREFIX}/wasi-sdk/share/wasi-sysroot/lib/wasm32-wasi'])

# utilities are NOT included, please install them by yourself:
#   deno, nodejs, bun, binaryen, wabt, wasmtime, wasmedge, wazero

def setup_proot():
    pass

def setup_wasm_run():
    pass

def write_to_github_script():
    # TODO: add_to_github_path.sh
    pass

# should sync with setup.sh
cc_opts  = '-fno-strict-aliasing -Wno-error=implicit-function-declaration -Wno-error=int-conversion -O3 -msimd128 -mnontrapping-fptoint -msign-ext -mbulk-memory -mmutable-globals -mmultivalue -mreference-types'
cxx_opts = '-fno-exceptions -fno-strict-aliasing -Wno-error=implicit-function-declaration -Wno-error=int-conversion -O3 -msimd128 -mnontrapping-fptoint -msign-ext -mbulk-memory -mmutable-globals -mmultivalue -mreference-types'
ld_opts  = '-Wl,--compress-relocations,--error-limit=0,--growable-table,--keep-section=ghc_wasm_jsffi,--stack-first,--strip-debug '

_EXTRA_ENVS = {
  'CONF_CC_OPTS_STAGE2': cc_opts,
  'CONF_CXX_OPTS_STAGE2': cxx_opts,
  'CONF_GCC_LINKER_OPTS_STAGE2': ld_opts,
  'CONF_CC_OPTS_STAGE1': cc_opts,
  'CONF_CXX_OPTS_STAGE1': cxx_opts,
  'CONF_GCC_LINKER_OPTS_STAGE1': ld_opts,
  # 'CONFIGURE_ARGS': "",
  # 'CROSS_EMULATOR': f'{PREFIX}/wasm-run/bin/wasm-run.mjs',
}

# --prefix is defined part of the configure command
configure_args = f'--host={HOST_VARS.HOST} --target=wasm32-wasi --with-intree-gmp --with-system-libffi'


def check_compilers():
    wasi_which = partial(which, path=f'{WASI_SDK_ROOT}/bin:' + os.environ.get('PATH'))

    envs = {
      'AR': wasi_which('llvm-ar'),
      'CC': wasi_which('clang'),
      'CC_FOR_BUILD': 'cc',
      'CXX': wasi_which('clang++'),
      'LD': wasi_which('wasm-ld'),
      'NM': wasi_which('llvm-nm'),
      'OBJCOPY': wasi_which('llvm-objcopy'),
      'OBJDUMP': wasi_which('llvm-objdump'),
      'RANLIB': wasi_which('llvm-ranlib'),
      'SIZE': wasi_which('llvm-size'),
      'STRINGS': wasi_which('llvm-strings'),
      'STRIP': wasi_which('llvm-strip'),
      # but why?
      'LLC': which('false'),
      'OPT': which('false'),
    }

    print('--- Checking compilers ---')

    env_ok = True

    for env, path in envs.items():
        print(f'Checking {env:14s}: ', end='')
        if path is None:
            print('[N/A]')
            env_ok = False
        else:
            print(path)

    return (env_ok, envs)

def write_env_files(envs):
    print('--- Writing the env file ---')

    with open(f'{PREFIX}/env', 'w') as envfile:
        # add to PATH if not exist; always add for non-supported shells
        envfile.write(f'prepend_path() {{\n')
        envfile.write(f'if ! (eval \'[[ 1 ]]\' 2>/dev/null) || [[ ":$PATH:" != *":$1:"* ]]; then\n')
        envfile.write(f'  export PATH="$1:$PATH"\n')
        envfile.write(f'fi\n')
        envfile.write(f'}}\n')
        envfile.write(f'prepend_path "{cabal_prefix}"\n')
        envfile.write(f'prepend_path "{WASI_SDK_ROOT}/bin"\n')
        envfile.write(f'prepend_path "{wasm_ghc_prefix}"\n')

        for env, value in envs.items():
            envfile.write(f'export {env}={value}\n')
            # write_to_github_script()

        for env, value in _EXTRA_ENVS.items():
            override = os.environ.get(env)
            if override is not None:
                value = override
            envfile.write(f'export {env}={quote(value)}\n')

def install_ghc():
    print('--- Downloading ghc ---')
    if path_is_fresh(GHC_TMP_DIR):
        run_cmd(['mkdir', '-p', GHC_TMP_DIR])
        if OS == 'Linux' and ARCH == 'x86_64':
            run_curl(jq_autogen(HOST_VARS.GHC), GHC_TMP_DIR, pipe_to='tar xJ -C %s --strip-components=1')
        else:
            run_curl(jq_autogen(HOST_VARS.GHC), GHC_TMP_DIR, pipe_to='tar x --zstd -C %s --strip-components=1')

    print('--- Configuring ghc ---')
    # TODO: allow skip
    envpath = f'{PREFIX}/env'
    run_cmd(
        f'. {quote(envpath)} && truncate -s0 ghc.log && ' +
        f'./configure {configure_args} --prefix={quote(wasm_ghc_prefix)} | tee ghc.log && ' +
        f'exec make install | tee ghc.log',
        cwd=GHC_TMP_DIR)

def setup_cabal():
    print('--- Downloading cabal ---')
    cabal_dest = f'{PREFIX}/cabal/bin'
    if path_is_fresh(cabal_dest):
        run_cmd(['mkdir', '-p', cabal_dest])
        run_curl(jq_autogen(HOST_VARS.CABAL), cabal_dest, pipe_to='tar xJ -C %s cabal')

    print('--- Configuring cabal wrapper for WASM ---')
    wasm_cabal = f'{cabal_prefix}/wasm32-wasi-cabal'
    cabal_dir = f'{PREFIX}/.cabal'

    if os.path.exists(wasm_cabal):
        print(f'Found "{wasm_cabal}". Skip writing cabal wrapper...')
    else:
        run_cmd(['mkdir', '-p', cabal_prefix])

        with open(wasm_cabal, 'w') as f:
            f.write('#!/bin/sh\n')

            cabal_exe = f'{PREFIX}/cabal/bin/cabal'
            wasm_ghc = f'{wasm_ghc_prefix}/bin/wasm32-wasi-ghc'
            wasm_hcpkg = f'{wasm_ghc_prefix}/bin/wasm32-wasi-ghc-pkg'
            wasm_hsc2hs = f'{wasm_ghc_prefix}/bin/wasm32-wasi-hsc2hs'

            f.write('\\\n'.join([
                f'CABAL_DIR={quote(cabal_dir)} ',
                f'exec ',
                f'{quote(cabal_exe)} ',
                f'--with-compiler={quote(wasm_ghc)} ',
                f'--with-hc-pkg={quote(wasm_hcpkg)} ',
                f'--with-hsc2hs={quote(wasm_hsc2hs)} ',
                '${1+"$@"}']) + '\n')

        run_cmd(['chmod', '755', wasm_cabal])

    if os.path.exists(f'{cabal_dir}/config'):
        print(f'Cabal dir "{cabal_dir}" is already configured. Skipping...')
    else:
        run_cmd(['mkdir', '-p', cabal_dir])
        if HOST_VARS.FLAVOUR not in {'9.6', '9.8', '9.10'}:
            print(f'Flavour {HOST_VARS.FLAVOUR} requires copying config from repo')
            run_cmd(['cp', f'{REPO}/cabal.config', f'{PREFIX}/.cabal/config'])
        run_cmd([wasm_cabal, 'update'],
                cwd=GHC_TMP_DIR)

# ------ main logic ------

if __name__ == '__main__':
    setup_wasi_sdk()
    env_ok, envs = check_compilers()
    if not env_ok:
        print('Aborting due to missing executables.')
        sys.exit(1)
    write_env_files(envs)

    if 0:
        print(f'Source "{PREFIX}/env" and then configure ghc with:')
        print(f'    ./configure {configure_args}')
    else:
        install_ghc()
        setup_cabal()
        print(f'All set! Source "{PREFIX}/env" to update your environment.')
    print('Done.')
