from conan import ConanFile
from enum import Enum
from conan import ConanFile
from conan.tools.gnu import Autotools, AutotoolsToolchain
from conan.tools.layout import basic_layout
from conan.tools.files import copy, get
from conan.tools.build import check_max_cppstd
from conan.errors import ConanInvalidConfiguration
import os

class LcovConan(ConanFile):
    name = "lcov"
    description = "LCOV is a graphical front-end for GCC's coverage testing tool gcov."
    topics = ("lcov", "c", "c++", "coverage", "gcov")
    license = "GPL-2.0"
    homepage = "https://github.com/linux-test-project/lcov/"
    url = "https://github.com/conan-io/conan-center-index"
    settings = "os"
    package_type = "application"
    options = {
        "prefix": ["ANY"]
    }
    default_options = {
        "prefix": "/usr/local"
    }

    def validate(self):
        if self.settings.os == "Windows":
            raise ConanInvalidConfiguration("Windows is not supported")

    def requirements(self):
        self.requires("libmemory-process-perl/0.06", run=True, headers=False, libs=False)

    def layout(self):
        self.folders.build = self.folders.source

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        tc = AutotoolsToolchain(self, prefix=self.options.prefix)
        tc.generate()

    def package(self):
        autotools = Autotools(self)
        autotools.install(args=[f"PREFIX={self.options.prefix}"])

        copy(
            self,
            pattern="COPYING*",
            dst=os.path.join(self._get_rel_prefix_path(), "licenses"),
            src=self.source_folder,
            keep_path=False,
        )

    def _get_rel_prefix_path(self):
        return os.path.join(self.package_folder, os.path.relpath(str(self.options.prefix), "/"))
