from os import mkdir
from pathlib import Path
from conan.api.conan_api import ConanAPI
from conans.model.recipe_ref import RecipeReference
from conans.util.files import rmdir, remove
from conan.errors import ConanException
import shutil
import subprocess

def patch_rpath(target_rpath: str, bin_path: Path):
    command = ["patchelf", "--force-rpath", "--set-rpath", target_rpath, bin_path]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        ConanException(f"Error executing command: {process.stderr}")


def archive_hook(pkg: RecipeReference, deploy_folder: Path, conan_api: ConanAPI):
    rmdir(deploy_folder / 'include')
    remove(deploy_folder / 'bin' / 'xxhsum')

    shutil.move(deploy_folder / 'lib', deploy_folder / 'mold_lib')
    mkdir(deploy_folder / 'lib')
    shutil.move(deploy_folder / 'mold_lib', deploy_folder / 'lib' / 'ds-mold')

    for x in (deploy_folder / 'lib').glob('*.so'):
        patch_rpath('$ORIGIN', x)

    for x in (deploy_folder / 'bin').glob('*'):
        patch_rpath('$ORIGIN/../lib/ds-mold', x)
