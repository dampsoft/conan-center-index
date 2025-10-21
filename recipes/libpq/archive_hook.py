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

from conan.tools.files import rmdir, rm as remove

def archive_hook(pkg: RecipeReference, deploy_folder: Path, conan_api: ConanAPI):
    out = ConanOutput()

    rmdir(conanfile=None, path=deploy_folder / 'include')
    remove(conanfile=None, pattern=deploy_folder / 'bin' / 'xxhsum')

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
