import os
from enum import Enum
from conan import ConanFile
from conan.tools.gnu import Autotools, AutotoolsToolchain
from conan.tools.layout import basic_layout
from conan.tools.files import copy, get
from conan.tools.build import check_max_cppstd
from conan.errors import ConanInvalidConfiguration


class ValgrindConan(ConanFile):
    name = "valgrind"
    topics = ("valgrind", "c", "c++")
    homepage = "https://valgrind.org/"
    url = "https://github.com/conan-io/conan-center-index"
    license = "GPL-2.0"
    settings = "os", "compiler", "build_type", "arch"
    package_type = "application"
    options = {
        "with_lto": [True, False],
        "prefix": ["ANY"]
    }
    default_options = {
        "with_lto": False,
        "prefix": "/usr/local/"
    }


    def validate(self):
        # See https://valgrind.org/info/platforms.html
        class SupportedOs(Enum):
            LINUX = "Linux"
            MACOS = "Macos"
            ANDROID = "Android"
            FREEBSD = "FreeBSD"
        class SupportedArch(Enum):
            X86 = "x86"
            X86_64 = "x86_64"
            ARMV7 = "armv7"
            ARMV8 = "armv8"
            PPC32 = "ppc32"
            PPC64 = "ppc64"
            PPC64LE = "ppc64le"
            S390X = "s390x"
            MIPS = "mips"
            MIPS64 = "mips64"

        supported_os = [v.value for v in SupportedOs]
        supported_arch = [v.value for v in SupportedArch]

        os_with_arch = {
            # Linux supports all architectures
            SupportedOs.LINUX.value: supported_arch,
            # MacOS currently only supports x86 and x86_64, no M1/ARM support yet
            SupportedOs.MACOS.value: [SupportedArch.X86.value, SupportedArch.X86_64.value],
            SupportedOs.ANDROID.value: [SupportedArch.ARMV7.value, SupportedArch.ARMV8.value, SupportedArch.X86.value, SupportedArch.MIPS.value],
            SupportedOs.FREEBSD.value: [SupportedArch.X86.value, SupportedArch.X86_64.value]
        }

        if self.settings.os not in supported_os:
            raise ConanInvalidConfiguration("Building Valgrind is only supported on {}.", ", ".join(supported_os))
        if self.settings.arch not in os_with_arch[str(self.settings.os)]:
            raise ConanInvalidConfiguration("Building Valgrind on {} is only supported on {}.", self.settings.os, ", ".join(supported_arch))
        
        # Valgrind's code, more specifically a compiler feature check when running configure, is not compatible with C++20
        check_max_cppstd(self, "17")

    def layout(self):
        basic_layout(self)

    def generate(self):
        tc = AutotoolsToolchain(self, prefix=self.options.prefix)

        # These are set by Valgrind already. Setting them again via AutotoolsToolchain causes errors during compilation when compiling both 32bit and 64bit targets
        flags_to_remove = ["-m32", "-m64", "-g"]

        env = tc.environment()

        for flag in flags_to_remove:
            try:
                env.remove("CXXFLAGS", flag) 
                env.remove("CFLAGS", flag) 
                env.remove("LDFLAGS", flag)
            # `flag` is not present in the specific env var, we ignore this
            except ValueError:
                pass

        tc.generate(env)

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def build(self):
        autotools = Autotools(self)
        autotools.configure(args=["--enable-lto=yes"] if self.options.with_lto else None)
        autotools.make()

    def package(self):
        autotools = Autotools(self)
        autotools.install()

        copy(
            self,
            pattern="COPYING*",
            dst=os.path.join(self._get_rel_prefix_path(), "licenses"),
            src=self.source_folder,
            keep_path=False,
        )

    def package_info(self):
        # As Valgrind bakes paths to libs etc. into the binary, we need to set VALGRIND_LIB to the package folder
        # Without this, we cannot execute the Valgrind package test, as Valgrind won't be able to find its libraries
        self.buildenv_info.define("VALGRIND_LIB", os.path.join(self._get_rel_prefix_path(), "libexec/valgrind"))

    def _get_rel_prefix_path(self):
        return os.path.join(self.package_folder, os.path.relpath(str(self.options.prefix), "/"))
