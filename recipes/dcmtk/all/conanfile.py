from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.build import can_run
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.files import apply_conandata_patches, export_conandata_patches, get, rmdir, save, copy
from conan.tools.microsoft import is_msvc, msvc_runtime_flag
from conan.tools.scm import Version
import os
import textwrap

required_conan_version = ">=1.53.0"


class DCMTKConan(ConanFile):
    name = "dcmtk"
    description = "DCMTK is a collection of libraries and applications implementing large parts the DICOM standard"
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://dicom.offis.de/dcmtk"
    license = "BSD-3-Clause"
    topics = ("dicom", "image")

    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "with_applications": [True, False],
        "with_multithreading": [True, False],
        "charset_conversion": [None, "libiconv", "icu"],
        "with_libxml2": [True, False],
        "with_zlib": [True, False],
        "with_openssl": [True, False],
        "with_libpng": [True, False],
        "with_libtiff": [True, False],
        "with_tcpwrappers": [True, False],
        "builtin_dictionary": [None, True, False],
        "builtin_private_tags": [True, False],
        "external_dictionary": [None, True, False],
        "wide_io": [True, False],
        "enable_stl": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "with_applications": False,
        "with_multithreading": True,
        "charset_conversion": "libiconv",
        "with_libxml2": True,
        "with_zlib": True,
        "with_openssl": True,
        "with_libpng": True,
        "with_libtiff": True,
        "with_tcpwrappers": False,
        "builtin_dictionary": None,
        "builtin_private_tags": False,
        "external_dictionary": None,
        "wide_io": False,
        "enable_stl": True,
    }

    def layout(self):
        cmake_layout(self, src_folder="src")

    def export_sources(self):
        export_conandata_patches(self)

    def config_options(self):
        if self.settings.os == "Windows":
            self.options.rm_safe("fPIC")
            self.options.rm_safe("with_tcpwrappers")

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")

    def requirements(self):
        if self.options.charset_conversion == "libiconv":
            self.requires("libiconv/1.17")
        elif self.options.charset_conversion == "icu":
            self.requires("icu/72.1")
        if self.options.with_libxml2:
            self.requires("libxml2/2.10.3")
        if self.options.with_zlib:
            self.requires("zlib/1.2.13")
        if self.options.with_openssl:
            self.requires("openssl/1.1.1t")
        if self.options.with_libpng:
            self.requires("libpng/1.6.39")
        if self.options.with_libtiff:
            self.requires("libtiff/4.4.0")
        if self.options.get_safe("with_tcpwrappers"):
            self.requires("tcp-wrappers/7.6")

    @property
    def _compilers_minimum_version(self):
        return {
            "gcc": "7",
            "Visual Studio": "16",
            "msvc": "192",
            "clang": "7",
            "apple-clang": "10",
        }

    def validate(self):
        if not can_run(self) and self.settings.os == "Macos" and self.settings.arch == "armv8":
            # FIXME: Probable issue with flags, build includes header 'mmintrin.h'
            raise ConanInvalidConfiguration("Cross building to Macos M1 is not supported (yet)")

        minimum_version = self._compilers_minimum_version.get(str(self.settings.compiler), False)
        if minimum_version and Version(self.settings.compiler.version) < minimum_version:
            raise ConanInvalidConfiguration(
                f"{self.ref} requires C++11, which your compiler does not support."
            )

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        tc = CMakeToolchain(self)

        # DICOM Data Dictionaries are required
        tc.variables["CMAKE_INSTALL_DATADIR"] = self._dcm_datadictionary_path

        tc.variables["BUILD_APPS"] = self.options.with_applications
        tc.variables["DCMTK_WITH_ICONV"] = self.options.charset_conversion == "libiconv"
        if self.options.charset_conversion == "libiconv":
            tc.variables["WITH_LIBICONVINC"] = self.dependencies["libiconv"].package_folder
        tc.variables["DCMTK_WITH_ICU"] = self.options.charset_conversion == "icu"
        tc.variables["DCMTK_WITH_OPENJPEG"] = False
        tc.variables["DCMTK_WITH_OPENSSL"] = self.options.with_openssl
        if self.options.with_openssl:
            tc.variables["WITH_OPENSSLINC"] = self.dependencies["openssl"].package_folder
        tc.variables["DCMTK_WITH_PNG"] = self.options.with_libpng
        if self.options.with_libpng:
            tc.variables["WITH_LIBPNGINC"] = self.dependencies["libpng"].package_folder
        tc.variables["DCMTK_WITH_SNDFILE"] = False
        tc.variables["DCMTK_WITH_THREADS"] = self.options.with_multithreading
        tc.variables["DCMTK_WITH_TIFF"] = self.options.with_libtiff
        if self.options.with_libtiff:
            tc.variables["WITH_LIBTIFFINC"] = self.dependencies["libtiff"].package_folder
        if self.settings.os != "Windows":
            tc.variables["DCMTK_WITH_WRAP"] = self.options.with_tcpwrappers
        tc.variables["DCMTK_WITH_XML"] = self.options.with_libxml2
        if self.options.with_libxml2:
            tc.variables["WITH_LIBXMLINC"] = self.dependencies["libxml2"].package_folder
            if "shared" in self.options["libxml2"]:
                tc.variables["WITH_LIBXML2_SHARED"] = self.options["libxml2"].shared
        tc.variables["DCMTK_WITH_ZLIB"] = self.options.with_zlib
        if self.options.with_zlib:
            tc.variables["WITH_ZLIBINC"] = self.dependencies["zlib"].package_folder

        tc.variables["DCMTK_ENABLE_STL"] = self.options.enable_stl
        tc.variables["DCMTK_ENABLE_CXX11"] = True

        tc.variables["DCMTK_ENABLE_MANPAGE"] = False
        tc.variables["DCMTK_WITH_DOXYGEN"] = False

        tc.variables["DCMTK_ENABLE_PRIVATE_TAGS"] = self.options.builtin_private_tags
        if self.options.external_dictionary is not None:
            if Version(self.version) < "3.6.7":
                tc.variables["DCMTK_ENABLE_EXTERNAL_DICTIONARY"] = self.options.external_dictionary
            else:
                tc.variables["DCMTK_DEFAULT_DICT"] = self.options.external_dictionary
        if self.options.builtin_dictionary is not None:
            tc.variables["DCMTK_ENABLE_BUILTIN_DICTIONARY"] = self.options.builtin_dictionary
        tc.variables["DCMTK_WIDE_CHAR_FILE_IO_FUNCTIONS"] = self.options.wide_io
        tc.variables["DCMTK_WIDE_CHAR_MAIN_FUNCTION"] = self.options.wide_io

        if self.settings.os == "Windows":
            tc.variables["DCMTK_OVERWRITE_WIN32_COMPILER_FLAGS"] = False

        if is_msvc(self):
            tc.variables["DCMTK_ICONV_FLAGS_ANALYZED"] = True
            tc.variables["DCMTK_COMPILE_WIN32_MULTITHREADED_DLL"] = "MD" in msvc_runtime_flag(self)

        tc.generate()

        deps = CMakeDeps(self)
        deps.set_property("openssl", "cmake_file_name", "OPENSSL")
        deps.set_property("libiconv", "cmake_file_name", "ICONV")
        deps.set_property("libiconv", "cmake_find_mode", "both")
        deps.generate()

    def build(self):
        apply_conandata_patches(self)
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        copy(self, pattern="COPYRIGHT", dst=os.path.join(self.package_folder, "licenses"), src=self.source_folder)

        cmake = CMake(self)
        cmake.install()

        rmdir(self, os.path.join(self.package_folder, "cmake"))
        rmdir(self, os.path.join(self.package_folder, "lib", "cmake"))
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rmdir(self, os.path.join(self.package_folder, "etc"))
        rmdir(self, os.path.join(self.package_folder, "share"))

        self._create_cmake_module_alias_targets(
            os.path.join(self.package_folder, self._module_file_rel_path),
            {target: f"DCMTK::{target}" for target in self._dcmtk_components}
        )

    def _create_cmake_module_alias_targets(self, module_file, targets):
        content = ""
        for alias, aliased in targets.items():
            content += textwrap.dedent("""\
                if(TARGET {aliased} AND NOT TARGET {alias})
                    add_library({alias} INTERFACE IMPORTED)
                    set_property(TARGET {alias} PROPERTY INTERFACE_LINK_LIBRARIES {aliased})
                endif()
            """.format(alias=alias, aliased=aliased))
        save(self, module_file, content)

    @property
    def _module_subfolder(self):
        return os.path.join("lib", "cmake")

    @property
    def _module_file_rel_path(self):
        return os.path.join(self._module_subfolder, "conan-official-{self.name}-targets.cmake")

    @property
    def _dcmtk_components(self):
        def charset_conversion():
            if bool(self.options.charset_conversion):
                return ["libiconv::libiconv"] if self.options.charset_conversion == "libiconv" else ["icu::icu"]
            return []

        def zlib():
            return ["zlib::zlib"] if self.options.with_zlib else []

        def png():
            return ["libpng::libpng"] if self.options.with_libpng else []

        def tiff():
            return ["libtiff::libtiff"] if self.options.with_libtiff else []

        def openssl():
            return ["openssl::openssl"] if self.options.with_openssl else []

        def tcpwrappers():
            return ["tcp-wrappers::tcp-wrappers"] if self.options.get_safe("with_tcpwrappers") else []

        def xml2():
            return ["libxml2::libxml2"] if self.options.with_libxml2 else []

        charls = "dcmtkcharls" if Version("3.6.6") <= self.version else "charls"

        return {
            "ofstd"   : charset_conversion(),
            "oflog"   : ["ofstd"],
            "dcmdata" : ["ofstd", "oflog"] + zlib(),
            "i2d"     : ["dcmdata"],
            "dcmimgle": ["ofstd", "oflog", "dcmdata"],
            "dcmimage": ["oflog", "dcmdata", "dcmimgle"] + png() + tiff(),
            "dcmjpeg" : ["ofstd", "oflog", "dcmdata", "dcmimgle", "dcmimage", "ijg8", "ijg12", "ijg16"],
            "ijg8"    : [],
            "ijg12"   : [],
            "ijg16"   : [],
            "dcmjpls" : ["ofstd", "oflog", "dcmdata", "dcmimgle", "dcmimage", charls],
            charls    : ["ofstd", "oflog"],
            "dcmtls"  : ["ofstd", "dcmdata", "dcmnet"] + openssl(),
            "dcmnet"  : ["ofstd", "oflog", "dcmdata"] + tcpwrappers(),
            "dcmsr"   : ["ofstd", "oflog", "dcmdata", "dcmimgle", "dcmimage"] + xml2(),
            "cmr"     : ["dcmsr"],
            "dcmdsig" : ["ofstd", "dcmdata"] + openssl(),
            "dcmwlm"  : ["ofstd", "dcmdata", "dcmnet"],
            "dcmqrdb" : ["ofstd", "dcmdata", "dcmnet"],
            "dcmpstat": ["ofstd", "oflog", "dcmdata", "dcmimgle", "dcmimage", "dcmnet", "dcmdsig", "dcmtls", "dcmsr", "dcmqrdb"] + openssl(),
            "dcmrt"   : ["ofstd", "oflog", "dcmdata", "dcmimgle"],
            "dcmiod"  : ["dcmdata", "ofstd", "oflog"],
            "dcmfg"   : ["dcmiod", "dcmdata", "ofstd", "oflog"],
            "dcmseg"  : ["dcmfg", "dcmiod", "dcmdata", "ofstd", "oflog"],
            "dcmtract": ["dcmiod", "dcmdata", "ofstd", "oflog"],
            "dcmpmap" : ["dcmfg", "dcmiod", "dcmdata", "ofstd", "oflog"],
        }

    @property
    def _dcm_datadictionary_path(self):
        return os.path.join(self.package_folder, "bin", "share")

    def package_info(self):
        self.cpp_info.set_property("cmake_find_mode", "both")
        self.cpp_info.set_property("cmake_file_name", "DCMTK")

        self.cpp_info.names["cmake_find_package"] = "DCMTK"
        self.cpp_info.names["cmake_find_package_multi"] = "DCMTK"

        def register_components(components):
            for target_lib, requires in components.items():
                self.cpp_info.components[target_lib].set_property("cmake_target_name", target_lib)
                self.cpp_info.components[target_lib].libs = [target_lib]
                self.cpp_info.components[target_lib].includedirs.append(os.path.join("include", "dcmtk"))
                self.cpp_info.components[target_lib].requires = requires

                # TODO: to remove in conan v2 once cmake_find_package* generators removed
                self.cpp_info.components[target_lib].names["cmake_find_package"] = target_lib
                self.cpp_info.components[target_lib].names["cmake_find_package_multi"] = target_lib
                self.cpp_info.components[target_lib].builddirs.append(self._module_subfolder)
                self.cpp_info.components[target_lib].build_modules["cmake_find_package"] = [self._module_file_rel_path]
                self.cpp_info.components[target_lib].build_modules["cmake_find_package_multi"] = [self._module_file_rel_path]

            if self.settings.os == "Windows":
                self.cpp_info.components["ofstd"].system_libs.extend([
                    "iphlpapi", "ws2_32", "netapi32", "wsock32"
                ])
            elif self.settings.os in ["Linux", "FreeBSD"]:
                self.cpp_info.system_libs.extend("nsl")
                self.cpp_info.components["ofstd"].system_libs.append("m")
                if self.options.with_multithreading:
                    self.cpp_info.components["ofstd"].system_libs.append("pthread")

        register_components(self._dcmtk_components)

        dcmdictpath = os.path.join(self._dcm_datadictionary_path, "dcmtk", "dicom.dic")
        self.output.info(f"Settings DCMDICTPATH environment variable: {dcmdictpath}")
        self.runenv_info.define_path("DCMDICTPATH", dcmdictpath)
        self.env_info.DCMDICTPATH = dcmdictpath # remove in conan v2?

        if self.options.with_applications:
            self.buildenv_info.define_path("DCMDICTPATH", dcmdictpath)
            bin_path = os.path.join(self.package_folder, "bin")
            self.output.info(f"Appending PATH environment variable: {bin_path}")
            self.env_info.PATH.append(bin_path)
