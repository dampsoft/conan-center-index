import os
from enum import Enum
from conan import ConanFile
from conan.tools.gnu import Autotools, AutotoolsToolchain
from conan.tools.layout import basic_layout
from conan.tools.files import copy, get
from conan.tools.build import check_max_cppstd
from conan.errors import ConanInvalidConfiguration

class LibmemoryProcessPerlConan(ConanFile):
    name = "libmemory-process-perl"
    description = "Perl extension for examining the memory of a process"
    topics = ("libmemory-process-perl", "memory", "process", "perl")
    homepage = "https://github.com/michal-josef-spacek/Memory-Process"
    url = "https://github.com/conan-io/conan-center-index"
    settings = "os"
    license: "BSD-2-Clause"
    package_type = "library"
    options = {
        "prefix": ["ANY"],
        "shared": [True, False]
    }
    default_options = {
        "prefix": "/usr/local",
        "shared": True
    }

    def validate(self):
        # See https://github.com/michal-josef-spacek/Memory-Process/blob/master/Makefile.PL#L33 for supported OS
        if self.settings.os not in ["Linux"]:
            print(self.settings.os)
            raise ConanInvalidConfiguration("libmemory-process-perl is only supported on Linux")

    def layout(self):
        self.folders.build = self.folders.source

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        self.run("perl Makefile.PL PREFIX={}".format(self.options.prefix))

        tc = AutotoolsToolchain(self, prefix=self.options.prefix)
        tc.generate()

    def build(self):
        autotools = Autotools(self)
        autotools.make()

    def package(self):
        autotools = Autotools(self)
        autotools.install()
