from conan.tools.microsoft import is_msvc, msvc_runtime_flag
from conan.tools.files import rename, get, apply_conandata_patches, replace_in_file, rmdir, rm
from conan.tools.build import cross_building
from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.apple import is_apple_os
from conan.tools.build import check_min_cppstd, cross_building, stdcpp_library
from conan.tools.cmake import CMake, CMakeToolchain, CMakeDeps, cmake_layout
from conan.tools.env import VirtualRunEnv, VirtualBuildEnv
from conan.tools.files import rename, get, apply_conandata_patches, replace_in_file, rmdir, rm, export_conandata_patches, copy, mkdir
from conan.tools.gnu import PkgConfigDeps
from conan.tools.microsoft import is_msvc, is_msvc_static_runtime
from conan.tools.scm import Version
from conan.tools.apple import is_apple_os
from conans import CMake, tools
import functools
import os

required_conan_version = ">=1.51.3"


class LibMysqlClientCConan(ConanFile):
    name = "libmysqlclient"
    description = "A MySQL client library for C development."
    license = "GPL-2.0"
    url = "https://github.com/conan-io/conan-center-index"
    topics = ("mysql", "sql", "connector", "database")
    homepage = "https://dev.mysql.com/downloads/mysql/"

    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "with_ssl": [True, False, "deprecated"],
        "with_zlib": [True, False, "deprecated"],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "with_ssl": "deprecated",
        "with_zlib": "deprecated",
    }

    short_paths = True
    generators = "cmake", "pkg_config"

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    @property
    def _with_zstd(self):
        return Version(self.version) > "8.0.17"

    @property
    def _with_lz4(self):
        return Version(self.version) > "8.0.17"

    @property
    def _min_cppstd(self):
        return "17" if Version(self.version) >= "8.0.27" else "11"

    @property
    def _compilers_minimum_version(self):
        return {
            "Visual Studio": "16" if Version(self.version) > "8.0.17" else "15",
            "gcc": "7" if Version(self.version) >= "8.0.27" else "5.3",
            "clang": "6",
        }

    def export_sources(self):
        self.copy("CMakeLists.txt")
        for patch in self.conan_data.get("patches", {}).get(self.version, []):
            self.copy(patch["patch_file"])

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        if self.options.shared:
            del self.options.fPIC
        if self.options.with_ssl != "deprecated":
            self.output.warn("with_ssl option is deprecated, do not use anymore. SSL cannot be disabled")
        if self.options.with_zlib != "deprecated":
            self.output.warn("with_zlib option is deprecated, do not use anymore. Zlib cannot be disabled")

    def package_id(self):
        del self.info.options.with_ssl
        del self.info.options.with_zlib

    def requirements(self):
        self.requires("openssl/3.0.8")
        self.requires("zlib/1.2.13")
        self.requires("zstd/1.5.5")
        self.requires("lz4/1.9.4")
        if self.settings.os == "FreeBSD":
            self.requires("libunwind/1.6.2")

    def validate(self):
        if self.settings.compiler.get_safe("cppstd"):
            check_min_cppstd(self, self._min_cppstd)

        def loose_lt_semver(v1, v2):
            lv1 = [int(v) for v in v1.split(".")]
            lv2 = [int(v) for v in v2.split(".")]
            min_length = min(len(lv1), len(lv2))
            return lv1[:min_length] < lv2[:min_length]

        minimum_version = self._compilers_minimum_version.get(str(self.settings.compiler), False)
        if minimum_version and loose_lt_semver(str(self.settings.compiler.version), minimum_version):
            raise ConanInvalidConfiguration(f"{self.ref} requires {self.settings.compiler} {minimum_version} or newer")

        if hasattr(self, "settings_build") and cross_building(self, skip_x64_x86=True):
            raise ConanInvalidConfiguration(
                "Cross compilation not yet supported by the recipe. contributions are welcome."
            )

        # FIXME: patch libmysqlclient 8.0.17 to support apple-clang >= 12?
        #        current errors:
        #             error: expected unqualified-id MYSQL_VERSION_MAJOR=8
        #             error: no member named 'ptrdiff_t' in the global namespace
        if (
            self.version == "8.0.17"
            and self.settings.compiler == "apple-clang"
            and Version(self.settings.compiler.version) >= "12.0"
        ):
            raise ConanInvalidConfiguration("libmysqlclient 8.0.17 doesn't support apple-clang >= 12.0")

        # mysql>=8.0.17 doesn't support shared library on MacOS.
        # https://github.com/mysql/mysql-server/blob/mysql-8.0.17/cmake/libutils.cmake#L333-L335
        if self.settings.compiler == "apple-clang" and self.options.shared:
            raise ConanInvalidConfiguration(f"{self.ref} doesn't support shared library")

        # mysql < 8.0.29 uses `requires` in source code. It is the reserved keyword in C++20.
        # https://github.com/mysql/mysql-server/blob/mysql-8.0.0/include/mysql/components/services/dynamic_loader.h#L270
        if self.settings.compiler.get_safe("cppstd") == "20" and Version(self.version) < "8.0.29":
            raise ConanInvalidConfiguration(f"{self.ref} doesn't support C++20")

    def build_requirements(self):
        if Version(self.version) >= "8.0.25" and is_apple_os(self):
            # CMake 3.18 or higher is required if Apple, but CI of CCI may run CMake 3.15
            self.tool_requires("cmake/3.25.3")
        if self.settings.os == "FreeBSD" and not self.conf.get("tools.gnu:pkg_config", check_type=str):
            self.tool_requires("pkgconf/1.9.3")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True, destination=self._source_subfolder)

    def _patch_files(self):
        apply_conandata_patches(self)

        libs_to_remove = ["icu", "libevent", "re2", "rapidjson", "protobuf", "libedit"]
        if not self._with_lz4:
            libs_to_remove.append("lz4")
        for lib in libs_to_remove:
            replace_in_file(
                self,
                os.path.join(self._source_subfolder, "CMakeLists.txt"),
                f"MYSQL_CHECK_{lib.upper()}()\n",
                "",
                strict=False,
            )
            replace_in_file(
                self, os.path.join(self._source_subfolder, "CMakeLists.txt"), f"INCLUDE({lib})\n", "", strict=False
            )
            replace_in_file(
                self,
                os.path.join(self._source_subfolder, "CMakeLists.txt"),
                f"WARN_MISSING_SYSTEM_{lib.upper()}({lib.upper()}_WARN_GIVEN)",
                f"# WARN_MISSING_SYSTEM_{lib.upper()}({lib.upper()}_WARN_GIVEN)",
                strict=False,
            )

            replace_in_file(
                self,
                os.path.join(self._source_subfolder, "CMakeLists.txt"),
                f"SET({lib.upper()}_WARN_GIVEN)",
                f"# SET({lib.upper()}_WARN_GIVEN)",
                strict=False,
            )

        rmdir(self, os.path.join(self._source_subfolder, "extra"))
        for folder in ["client", "man", "mysql-test", "libbinlogstandalone"]:
            rmdir(self, os.path.join(self._source_subfolder, folder))
            replace_in_file(
                self,
                os.path.join(self._source_subfolder, "CMakeLists.txt"),
                f"ADD_SUBDIRECTORY({folder})\n",
                "",
                strict=False,
            )
        rmdir(self, os.path.join(self._source_subfolder, "storage", "ndb"))
        for t in ["INCLUDE(cmake/boost.cmake)\n", "MYSQL_CHECK_EDITLINE()\n"]:
            replace_in_file(self, os.path.join(self.source_folder, "CMakeLists.txt"),
                            t,
                            "",
                            strict=False)

        # Upstream does not actually load lz4 directories for system, force it to
        replace_in_file(self, os.path.join(self.source_folder, "libbinlogevents", "CMakeLists.txt"),
                        "INCLUDE_DIRECTORIES(${CMAKE_SOURCE_DIR}/libbinlogevents/include)",
                        "MY_INCLUDE_SYSTEM_DIRECTORIES(LZ4)\nINCLUDE_DIRECTORIES(${CMAKE_SOURCE_DIR}/libbinlogevents/include)")

        replace_in_file(self, os.path.join(self.source_folder, "cmake", "zstd.cmake"),
                        "NAMES zstd",
                        f"NAMES zstd {self.dependencies['zstd'].cpp_info.aggregated_components().libs[0]}")

        replace_in_file(self, os.path.join(self.source_folder, "cmake", "ssl.cmake"),
                        "NAMES ssl",
                        f"NAMES ssl {self.dependencies['openssl'].cpp_info.components['ssl'].libs[0]}")

        replace_in_file(self, os.path.join(self.source_folder, "cmake", "ssl.cmake"),
                        "NAMES crypto",
                        f"NAMES crypto {self.dependencies['openssl'].cpp_info.components['crypto'].libs[0]}")

        replace_in_file(self, os.path.join(self.source_folder, "cmake", "ssl.cmake"),
                        "IF(NOT OPENSSL_APPLINK_C)\n",
                        "IF(FALSE AND NOT OPENSSL_APPLINK_C)\n",
                        strict=False)

        # Do not copy shared libs of dependencies to package folder
        deps_shared = ["SSL"]
        if Version(self.version) > "8.0.17":
            deps_shared.extend(["KERBEROS", "SASL", "LDAP", "PROTOBUF", "CURL"])
        for dep in deps_shared:
            replace_in_file(
                self, os.path.join(self._source_subfolder, "CMakeLists.txt"), f"MYSQL_CHECK_{dep}_DLLS()", ""
            )

        sources_cmake = os.path.join(self._source_subfolder, "CMakeLists.txt")
        sources_cmake_orig = os.path.join(self._source_subfolder, "CMakeListsOriginal.txt")
        rename(self, sources_cmake, sources_cmake_orig)
        rename(self, "CMakeLists.txt", sources_cmake)
        if self.settings.os == "Macos":
            replace_in_file(
                self,
                os.path.join(self._source_subfolder, "libmysql", "CMakeLists.txt"),
                "COMMAND %s"
                % ("$<TARGET_FILE:libmysql_api_test>" if Version(self.version) < "8.0.25" else "libmysql_api_test"),
                "COMMAND DYLD_LIBRARY_PATH=%s %s"
                % (
                    os.path.join(self.build_folder, "library_output_directory"),
                    os.path.join(self.build_folder, "runtime_output_directory", "libmysql_api_test"),
                ),
            )
        replace_in_file(
            self,
            os.path.join(self._source_subfolder, "cmake", "install_macros.cmake"),
            "  INSTALL_DEBUG_SYMBOLS(",
            "  # INSTALL_DEBUG_SYMBOLS(",
        )

    @functools.lru_cache(1)
    def _configure_cmake(self):
        cmake = CMake(self)
        cmake.definitions["DISABLE_SHARED"] = not self.options.shared
        cmake.definitions["STACK_DIRECTION"] = "-1"  # stack grows downwards, on very few platforms stack grows upwards
        cmake.definitions["WITHOUT_SERVER"] = True
        cmake.definitions["WITH_UNIT_TESTS"] = False
        cmake.definitions["ENABLED_PROFILING"] = False
        cmake.definitions["MYSQL_MAINTAINER_MODE"] = False
        cmake.definitions["WIX_DIR"] = False
        if self._with_lz4:
            cmake.definitions["WITH_LZ4"] = "system"

        if self._with_zstd:
            cmake.definitions["WITH_ZSTD"] = "system"
            cmake.definitions["ZSTD_INCLUDE_DIR"] = self.deps_cpp_info["zstd"].include_paths[0]

        if is_msvc(self):
            cmake.definitions["WINDOWS_RUNTIME_MD"] = "MD" in msvc_runtime_flag(self)

        cmake.definitions["WITH_SSL"] = self.deps_cpp_info["openssl"].rootpath

        cmake.definitions["WITH_ZLIB"] = "system"
        cmake.configure(source_dir=self._source_subfolder)
        return cmake

    def build(self):
        self._patch_files()
        cmake = self._configure_cmake()
        with tools.run_environment(self):
            cmake.build()

    def package(self):
        cmake = self._configure_cmake()
        with tools.run_environment(self):
            cmake.install()
        os.mkdir(os.path.join(self.package_folder, "licenses"))
        rename(
            self, os.path.join(self.package_folder, "LICENSE"), os.path.join(self.package_folder, "licenses", "LICENSE")
        )
        os.remove(os.path.join(self.package_folder, "README"))
        rm(self, "*.pdb", self.package_folder, recursive=True)
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rmdir(self, os.path.join(self.package_folder, "docs"))
        rmdir(self, os.path.join(self.package_folder, "share"))
        if self.settings.os == "Windows" and self.options.shared:
            self.copy("*.dll", "bin", keep_path=False)
        if self.options.shared:
            rm(self, "*.a", self.package_folder, recursive=True)
        else:
            rm(self, "*.dll", self.package_folder, recursive=True)
            rm(self, "*.dylib", self.package_folder, recursive=True)
            rm(self, "*.so*", self.package_folder, recursive=True)

    def package_info(self):
        self.cpp_info.set_property("pkg_config_name", "mysqlclient")
        self.cpp_info.names["pkg_config"] = "mysqlclient"
        self.cpp_info.libs = ["libmysql" if self.settings.os == "Windows" and self.options.shared else "mysqlclient"]
        if not self.options.shared:
            stdcpp_library = tools.stdcpp_library(self)
            if stdcpp_library:
                self.cpp_info.system_libs.append(stdcpp_library)
            if self.settings.os in ["Linux", "FreeBSD"]:
                self.cpp_info.system_libs.append("m")
        if self.settings.os in ["Linux", "FreeBSD"]:
            if Version(self.version) >= "8.0.25":
                self.cpp_info.system_libs.append("resolv")
        if self.settings.os == "Windows":
            if Version(self.version) >= "8.0.25":
                self.cpp_info.system_libs.append("dnsapi")
            self.cpp_info.system_libs.append("secur32")

        # TODO: There is no official FindMySQL.cmake, but it's a common Find files in many projects
        #       do we want to support it in CMakeDeps?
        self.cpp_info.names["cmake_find_package"] = "MySQL"
        self.cpp_info.names["cmake_find_package_multi"] = "MySQL"
