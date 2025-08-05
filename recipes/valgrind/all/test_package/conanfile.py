from io import StringIO
from pathlib import Path
from conan import ConanFile
from conan.tools.env import Environment
from conan.tools.build import can_run


class ValgrindTestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def test(self):
        if can_run(self):
            prefix = self.dependencies["valgrind"].options.prefix
            pkg_path = Path(self.dependencies["valgrind"].package_folder.replace("\\", "/"))
            pkg_path = Path(f"{pkg_path}/{prefix}")
            bin_path = Path(f"{pkg_path}/bin/valgrind")

            env = Environment()
            env.define("VALGRIND_LIB", str(Path(f"{pkg_path}/libexec/valgrind")))

            with env.vars(self).apply():
                self.run(f"{bin_path} --version", env="conanrun")
