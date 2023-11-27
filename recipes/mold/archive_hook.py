from pathlib import Path
from conan.api.conan_api import ConanAPI
from conans.model.recipe_ref import RecipeReference

def archive_hook(pkg: RecipeReference, deploy_folder: Path, conan_api: ConanAPI):
    pass

