from os import mkdir
import os
from pathlib import Path
from conan.api.conan_api import ConanAPI
from conans.model.recipe_ref import RecipeReference
from conan.errors import ConanException
from conan.cli.printers import ConanOutput
import shutil
import subprocess
from conan.cli.printers.graph import print_graph_packages


try:
    from conan.tools.files import rmdir, rm as remove
except ImportError:
    from conans.util.files import rmdir, remove

def patch_rpath(patchelf_path: str, target_rpath: str, bin_path: Path):
    command = [patchelf_path, "--force-rpath", "--set-rpath", target_rpath, bin_path]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        ConanException(f"Error executing command: {process.stderr}")

def install_patchelf(out: ConanOutput, deploy_folder: Path, conan_api: ConanAPI) -> str:
    out.info("Installing patchelf")

    enabled_remotes = conan_api.remotes.list()
    graph = conan_api.graph.load_graph_requires(
        requires=["patchelf/0.17.2"],
        tool_requires=None,
        lockfile=None,
        profile_build=conan_api.profiles.get_profile(
            profiles=[conan_api.profiles.get_default_build()]
        ),
        profile_host=conan_api.profiles.get_profile(
            profiles=[conan_api.profiles.get_default_host()]
        ),
        remotes=enabled_remotes,
        update=False,
    )
    graph.report_graph_error()

    conan_api.graph.analyze_binaries(graph, remotes=enabled_remotes, build_mode=["never"])
    print_graph_packages(graph)
    conan_api.install.install_binaries(deps_graph=graph)

    conan_api.install.install_consumer(
        deps_graph=graph,
        output_folder=str(deploy_folder/ 'patchelf'),
        source_folder=os.getcwd(),
        deploy=["ds_nexus_deploy"],
    )

    return deploy_folder / 'patchelf' / 'ds_nexus_deploy' / 'out'  / 'bin' / 'patchelf'

def archive_hook(pkg: RecipeReference, deploy_folder: Path, conan_api: ConanAPI):
    return

    out = ConanOutput()

    patchelf_path = install_patchelf(out, deploy_folder, conan_api)

    try:
        rmdir(conanfile=None, path=deploy_folder)
    except TypeError:
        rmdir(deploy_folder / 'include')

    try:
        remove(conanfile=None, pattern=deploy_folder / 'bin' / 'xxhsum')
    except TypeError:
        remove(deploy_folder / 'bin' / 'xxhsum')

    shutil.move(deploy_folder / 'lib', deploy_folder / 'mold_lib')
    mkdir(deploy_folder / 'lib')
    shutil.move(deploy_folder / 'mold_lib', deploy_folder / 'lib' / 'ds-mold')

    out.info("Patching RPATH in mold binaries")

    for x in (deploy_folder / 'lib').glob('*.so'):
        patch_rpath(patchelf_path, '$ORIGIN', x)

    for x in (deploy_folder / 'bin').glob('*'):
        patch_rpath(patchelf_path, '$ORIGIN/../lib/ds-mold', x)

    try:
        rmdir(conanfile=None, path=deploy_folder / 'patchelf')
    except TypeError:
        rmdir(deploy_folder / 'patchelf')

    out.success("Done, will generate archive now!")
