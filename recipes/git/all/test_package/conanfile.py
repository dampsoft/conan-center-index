import tempfile

from conan import ConanFile
from conan.tools.build import can_run

class MoldTestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def test(self):
        if can_run(self):
            self.run("git -v", env="conanrun")
            with tempfile.TemporaryDirectory() as repo:
                self.run(f'git init "{repo}"', env="conanrun")
                self.run(f'git -C "{repo}" submodule status', env="conanrun")
