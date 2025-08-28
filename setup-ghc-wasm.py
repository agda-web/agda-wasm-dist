import os
import subprocess
import shlex
from shlex import quote
from shutil import Error, which
import sys
import json
from collections import namedtuple
from functools import partial

# This script is a manual translation of ghc-wasm-meta's setup.sh.
# The snapshot of this script is based on is at (accessed around May 2025):
# https://gitlab.haskell.org/haskell-wasm/ghc-wasm-meta/-/blob/fe5573f28327d12a1c47ec61d6bbe0cc9d7983dd/setup.sh

# TODO: sed
for cmd in ['curl', 'unzip', 'tar', 'xz']:
    if which(cmd) is None:
        print(f'This script requires {cmd}')
        sys.exit(1)

print_err = partial(print, file=sys.stderr)
HostVars = namedtuple('HostVars', 'HOST WASI_SDK WASI_SDK_JOB_NAME WASI_SDK_ARTIFACT_PATH WASMTIME NODEJS CABAL BINARYEN GHC FLAVOUR')

REPO = os.environ['PWD']

def _log_cmd(is_shell, arg, **kwargs):
    if is_shell:
        print_err('+', arg, kwargs)
    else:
        print_err('+', shlex.join(arg), kwargs)

def run_cmd(arg, **kwargs):
    is_shell = isinstance(arg, str)
    _log_cmd(is_shell, arg, **kwargs)
    return subprocess.check_output(
        arg, **kwargs, shell=is_shell, universal_newlines=True
    ).strip()

def run_cmd_and_get_exit_code(arg, **kwargs):
    is_shell = isinstance(arg, str)
    _log_cmd(is_shell, arg, **kwargs)
    return subprocess.run(
        arg, **kwargs, shell=is_shell, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode

def jq_autogen(name):
    # cmd = f'''jq -r '."{name}".url' {REPO}/autogen.json'''
    # return run_cmd(cmd)
    with open(f'{REPO}/autogen.json') as f:
        data = json.load(f)
    return data[name]['url']

# TODO: remove pipe_to to mandate all output to be saved
def run_curl(url, dest, *, pipe_to=None, **kwargs):
    cmd = f'curl -f -L --retry 5 {quote(url)}'
    tail = '-o %s'
    if pipe_to is not None:
        tail = '| ' + pipe_to
    return run_cmd(cmd + ' ' + (tail % quote(dest)), **kwargs)

def curl_upstream_wasi_sdk_pipeline_id(upstreamWasiSdkPipelineId, targetJobName):
    url = f'https://gitlab.haskell.org/api/v4/projects/3212/pipelines/{upstreamWasiSdkPipelineId}/jobs?scope[]=success'
    output = run_cmd(f'curl {quote(url)}')
    jobs = json.loads(output)
    for job in jobs:
        if job['name'] == targetJobName:
            return job['id']
    raise Error(f'Cannot find the job with name "{targetJobName}" from the upstream WASI SDK pipeline.')

def path_is_fresh(s):
    if os.path.exists(s):
        print(f'Found "{s}", skip downloading...')
        return False
    return True


OS = run_cmd('uname -s')
ARCH = run_cmd('uname -m')
PREFIX = os.environ.get('PREFIX', run_cmd('realpath ' + quote(os.path.expandvars('$HOME/.ghc-wasm'))))
WASI_SDK_ROOT = f'{PREFIX}/wasi-sdk'

wasm_ghc_prefix = f'{PREFIX}/wasm32-wasi-ghc'
cabal_prefix = f'{PREFIX}/wasm32-wasi-cabal'


def host_specific():
    flavour = os.environ.get('FLAVOUR', '9.12')
    print(f'Selecting Host: ({OS}, {ARCH}) with flavour: "{flavour}"')

    if OS == 'Linux' and ARCH == 'x86_64':
        return HostVars(
            'x86_64-linux',
            'wasi-sdk',
            'x86_64-linux',
            'dist/wasi-sdk-26.0-x86_64-linux.tar.gz',
            'wasmtime',
            'nodejs',
            'cabal',
            'binaryen',
            f'wasm32-wasi-ghc-{flavour}',
            flavour)

    if OS == 'Linux' and ARCH == 'aarch64':
        if flavour not in {'9.10', '9.12'}:
            flavour += '###unsupported###'

        return HostVars(
            'aarch64-linux',
            'wasi-sdk-aarch64-linux',
            'aarch64-linux',
            'dist/wasi-sdk-26.0-aarch64-linux.tar.gz',
            'wasmtime_aarch64_linux',
            'nodejs_aarch64_linux',
            'cabal_aarch64_linux',
            'binaryen_aarch64_linux',
            f'wasm32-wasi-ghc-gmp-aarch64-linux-{flavour}',
            'flavour')

    if OS == 'Darwin' and ARCH == 'arm64':
        if flavour not in {'9.10', '9.12'}:
            flavour += '###unsupported###'

        return HostVars(
            'aarch64-apple-darwin',
            'wasi-sdk-aarch64-darwin',
            'aarch64-darwin',
            'dist/wasi-sdk-26.0-arm64-macos.tar.gz',
            'wasmtime_aarch64_darwin',
            'nodejs_aarch64_darwin',
            'cabal_aarch64_darwin',
            'binaryen_aarch64_darwin',
            f'wasm32-wasi-ghc-gmp-aarch64-darwin-{flavour}',
            flavour)

    if OS == 'Darwin' and ARCH == 'x86_64':
        flavour += '###unsupported###'

        return HostVars(
            'x86_64-apple-darwin',
            'wasi-sdk-x86_64-darwin',
            'x86_64-darwin',
            'dist/wasi-sdk-26.0-arm64-macos.tar.gz',
            'wasmtime_x86_64_darwin',
            'nodejs_x86_64_darwin',
            'cabal_x86_64_darwin',
            'binaryen_x86_64_darwin',
            'wasm32-wasi-ghc-gmp-x86_64-darwin',  # no prebuilt ghc available
            'gmp')

    print(f'Host not supported: ({OS}, {ARCH}, {flavour})')
    sys.exit(1)


HOST_VARS = host_specific()
# unused; to be used in wasm-run's setup
# BSD sed does not accept long options such as "--version".
# SED_IS_GNU = run_cmd_and_get_exit_code('sed --version') == 0
GHC_TMP_DIR = f'{REPO}/ghc.{HOST_VARS.FLAVOUR}'

# TODO: workdir; currently it unzips everything to the project dir and also use them to
# avoid redownloading, but it may cause problems on readonly filesystems.
# Since we do not have popd

def determine_wasi_sdk_bindist():
    UPSTREAM_WASI_SDK_PIPELINE_ID = os.environ.get('UPSTREAM_WASI_SDK_PIPELINE_ID', None)
    if UPSTREAM_WASI_SDK_PIPELINE_ID is not None:
        jobId = curl_upstream_wasi_sdk_pipeline_id(UPSTREAM_WASI_SDK_PIPELINE_ID, HOST_VARS.WASI_SDK_JOB_NAME)
        return f'https://gitlab.haskell.org/haskell-wasm/wasi-sdk/-/jobs/{jobId}/artifacts/raw/{HOST_VARS.WASI_SDK_ARTIFACT_PATH}'
    else:
        return jq_autogen(HOST_VARS.WASI_SDK)

def setup_wasi_sdk():
    print('--- Setting up WASI SDK ---')
    if path_is_fresh(WASI_SDK_ROOT):
        wasi_sdk_bindist = determine_wasi_sdk_bindist()
        print(f'Installing wasi-sdk from {wasi_sdk_bindist}')
        run_cmd(['mkdir', '-p', WASI_SDK_ROOT])
        run_curl(wasi_sdk_bindist, WASI_SDK_ROOT, pipe_to='tar xz -C %s --no-same-owner --strip-components=1')

    print('--- Setting up ffi-wasm ---')
    ffi_wasm_dest = f'out/libffi-wasm'
    if path_is_fresh(ffi_wasm_dest):
        run_curl(jq_autogen('libffi-wasm'), 'libffi-wasm.zip')
        run_cmd('unzip libffi-wasm.zip')

    run_cmd(['cp', '-a',
             'out/libffi-wasm/include/.',
             f'{PREFIX}/wasi-sdk/share/wasi-sysroot/include/wasm32-wasi'])
    run_cmd(['cp', '-a',
             'out/libffi-wasm/lib/.',
             f'{PREFIX}/wasi-sdk/share/wasi-sysroot/lib/wasm32-wasi'])

    print('--- Setting up binaryen ---')
    if path_is_fresh('binaryen/bin'):
        run_cmd(['mkdir', '-p', 'binaryen'])
        run_curl(jq_autogen('binaryen'), 'binaryen', pipe_to='tar xz -C %s --no-same-owner --strip-components=1')
        run_cmd(['cp', 'binaryen/bin/wasm-opt', f'{WASI_SDK_ROOT}/bin'])

# utilities are NOT included, please install them by yourself:
#   nodejs, playwright, wabt, wasmtime

def setup_wasm_run():
    pass

def write_to_github_script():
    # TODO: add_to_github_path.sh
    pass

# should sync with setup.sh
cc_opts  = '-Wno-error=int-conversion -O3 -mcpu=lime1 -mreference-types -msimd128 -mtail-call'
cxx_opts = '-fno-exceptions -Wno-error=int-conversion -O3 -mcpu=lime1 -mreference-types -msimd128 -mtail-call'
ld_opts  = '-Wl,--error-limit=0,--keep-section=ghc_wasm_jsffi,--keep-section=target_features,--stack-first,--strip-debug '

_EXTRA_ENVS = {
  'CONF_CC_OPTS_STAGE2': cc_opts,
  'CONF_CXX_OPTS_STAGE2': cxx_opts,
  'CONF_GCC_LINKER_OPTS_STAGE2': ld_opts,
  'CONF_CC_OPTS_STAGE1': cc_opts,
  'CONF_CXX_OPTS_STAGE1': cxx_opts,
  'CONF_GCC_LINKER_OPTS_STAGE1': ld_opts,
  # 'CONFIGURE_ARGS': "",
  # 'CROSS_EMULATOR': f'{PREFIX}/wasm-run/bin/wasm-run.mjs',
  # 'NODE_PATH': f'{PREFIX}/nodejs/lib/node_modules'
}

# --prefix is defined part of the configure command
configure_args = f'--host={HOST_VARS.HOST} --target=wasm32-wasi --with-intree-gmp --with-system-libffi'


def check_compilers():
    wasi_which = partial(which, path=f'{WASI_SDK_ROOT}/bin:' + os.environ.get('PATH', ''))

    envs = {
      'AR': wasi_which('llvm-ar'),
      'CC': wasi_which('wasm32-wasi-clang'),
      'CC_FOR_BUILD': 'cc',
      'CXX': wasi_which('wasm32-wasi-clang++'),
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
        envfile.write(f'prepend_path "{wasm_ghc_prefix}/bin"\n')

        for env, value in envs.items():
            envfile.write(f'export {env}={value}\n')
            # write_to_github_script()

        for env, value in _EXTRA_ENVS.items():
            override = os.environ.get(env)
            if override is not None:
                value = override
            envfile.write(f'export {env}={quote(value)}\n')

def install_ghc():
    if '###unsupported###' in HOST_VARS.FLAVOUR:
        raise Exception(
            f'No prebuilt GHC wasm bindist with flavour "{HOST_VARS.FLAVOUR[:HOST_VARS.FLAVOUR.find("#")]}" on {HOST_VARS.HOST}. ' +
            'You can still skip GHC and complete the setup.')

    print('--- Downloading ghc ---')
    if path_is_fresh(GHC_TMP_DIR):
        # TODO: support specifying UPSTREAM_GHC_PIPELINE_ID
        ghc_bindist = jq_autogen(HOST_VARS.GHC)
        print(f'Installing wasm32-wasi-ghc from {ghc_bindist}')
        run_cmd(['mkdir', '-p', GHC_TMP_DIR])
        run_curl(ghc_bindist, GHC_TMP_DIR, pipe_to='tar xJ -C %s --no-same-owner --strip-components=1')

    print('--- Configuring ghc ---')
    # TODO: allow skip
    envpath = f'{PREFIX}/env'
    run_cmd(
        f'. {quote(envpath)} && truncate -s0 ghc.log && ' +
        f'./configure {configure_args} --prefix={quote(wasm_ghc_prefix)} | tee ghc.log && ' +
        f'RelocatableBuild=YES exec make install | tee ghc.log',
        cwd=GHC_TMP_DIR)
    # TODO: wasm32-wasi-ghc-pkg recache

def setup_cabal():
    print('--- Downloading cabal ---')
    cabal_dest = f'{PREFIX}/cabal/bin'
    cabal_exe = f'{cabal_dest}/cabal'

    if path_is_fresh(cabal_exe):
        run_cmd(['mkdir', '-p', cabal_dest])
        run_curl(jq_autogen(HOST_VARS.CABAL), cabal_dest, pipe_to='tar xJ --no-same-owner -C %s cabal')

    print('--- Configuring cabal wrapper for WASM ---')
    wasm_cabal = f'{cabal_prefix}/wasm32-wasi-cabal'
    cabal_dir = f'{PREFIX}/.cabal'

    if os.path.exists(wasm_cabal):
        print(f'Found "{wasm_cabal}". Skip writing cabal wrapper...')
    else:
        run_cmd(['mkdir', '-p', cabal_prefix])

        with open(wasm_cabal, 'w') as f:
            f.write('#!/bin/sh\n')
            # echo 'PREFIX=$(realpath "$(dirname "$0")"/../..)'

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
        if HOST_VARS.FLAVOUR not in {'9.6', '9.8', '9.10', '9.12'}:
            print(f'Cabal with flavour {HOST_VARS.FLAVOUR} uses "head" config')
            run_cmd(['cp', f'{REPO}/cabal.head.config', f'{PREFIX}/.cabal/config'])
        elif HOST_VARS.FLAVOUR in {'9.10', '9.12'}:
            print(f'Cabal with flavour {HOST_VARS.FLAVOUR} uses "th" config')
            run_cmd(['cp', f'{REPO}/cabal.th.config', f'{PREFIX}/.cabal/config'])
        else:
            print(f'Cabal with flavour {HOST_VARS.FLAVOUR} uses "legacy" config')
            run_cmd(['cp', f'{REPO}/cabal.legacy.config', f'{PREFIX}/.cabal/config'])

    print('Updating cabal...')
    run_cmd([wasm_cabal, 'update'], cwd=GHC_TMP_DIR)

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
