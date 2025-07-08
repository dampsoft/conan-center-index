from io import StringIO
from pathlib import Path
from conan import ConanFile
from conan.tools.build import can_run


class ValgrindTestConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"

    def requirements(self):
        self.requires(self.tested_reference_str)

    def test(self):
        if can_run(self):
            prefix = self.dependencies["valgrind"].options.prefix
            bin_path = self.dependencies["valgrind"].package_folder.replace("\\", "/")
            bin_path = Path(f"{bin_path}/{prefix}/bin/valgrind")

            stdout, stderr = StringIO(), StringIO()
            self.run(f"{bin_path} --version", env="conanrun", stdout=stdout, stderr=stderr)

            print(stderr.getvalue())
            print(stdout.getvalue())
