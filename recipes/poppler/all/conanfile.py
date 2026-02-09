from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.apple import is_apple_os
from conan.tools.microsoft import is_msvc
from conan.tools.build import check_min_cppstd
from conan.tools.files import get, copy, rmdir, rm, apply_conandata_patches, export_conandata_patches
from conan.tools.env import VirtualBuildEnv, VirtualRunEnv
from conan.tools.build import cross_building
from conan.tools.cmake import CMake, CMakeToolchain, CMakeDeps, cmake_layout
from conan.tools.scm import Version
import os
import functools

required_conan_version = ">=2"


class PopplerConan(ConanFile):
    name = "poppler"
    description = "Poppler is a PDF rendering library based on the xpdf-3.0 code base"
    homepage = "https://poppler.freedesktop.org/"
    topics = "pdf", "rendering"
    license = "GPL-2.0-or-later", "GPL-3.0-or-later"
    url = "https://github.com/conan-io/conan-center-index"
    package_type = "library"

    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "cpp": [True, False],
        "fontconfiguration": ["generic", "fontconfig", "win32", "android"],
        "splash": [True, False],
        "float": [True, False],
        "with_cairo": [True, False],
        "with_glib": [True, False],
        "with_gobject_introspection": [True, False],
        "with_qt": [True, False],
        "with_libiconv": [True, False],
        "with_openjpeg": [True, False],
        "with_lcms": [True, False],
        "with_libjpeg": ["libjpeg", "libjpeg-turbo", False],
        "with_png": [True, False],
        "with_nss": [True, False],
        "with_tiff": [True, False],
        "with_libcurl": [True, False],
        "with_zlib": [True, False],
        # "with_qt": [True, False],
        # If you need control over these options, please open an issue
        # "with_openjpeg": [True, False],
        # "with_libjpeg": ["libjpeg", False],
        # "with_png": [True, False],
        # "with_gobject_introspection": [True, False],
        # "with_gtk": [True, False],
        # "with_nss": [True, False],
        # "float": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "cpp": True,
        "with_zlib": True,
        "with_libcurl": False,
        "splash": True,
        "with_lcms": False,
        "fontconfiguration": "generic",
        "with_cairo": False,
        "with_glib": False,
        "with_gobject_introspection": True,
        "with_qt": False,
        "with_libiconv": True,
        "with_openjpeg": True,
        "with_libjpeg": "libjpeg",
        "with_png": True,
        "with_nss": False,
        "with_tiff": True,
        "float": False,
    }
    implements = ["auto_shared_fpic"]

    def export_sources(self):
        export_conandata_patches(self)

    def layout(self):
        cmake_layout(self, src_folder="src")

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC
            self.options.fontconfiguration = "win32"
        elif self.settings.os == "Android":
            self.options.fontconfiguration = "android"

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")
        if not self.options.with_cairo:
            self.options.rm_safe("with_glib")
        if not self.options.get_safe("with_glib"):
            self.options.rm_safe("with_gobject_introspection")
        if self.options.cpp:
            if is_apple_os(self):
                self.options.with_libiconv = True
        else:
            self.options.rm_safe("with_libiconv")

    def requirements(self):
        self.requires("poppler-data/0.4.11")
        self.requires("freetype/2.13.3")
        if self.options.get_safe("with_libiconv"):
            self.requires("libiconv/1.18")
        if self.options.fontconfiguration == "fontconfig":
            self.requires("fontconfig/2.15.0")
        if self.options.with_cairo:
            self.requires("cairo/1.18.0")
        if self.options.get_safe("with_glib"):
            self.requires("glib/2.78.3")
        if self.options.get_safe("with_gobject_introspection"):
            self.requires("gobject-introspection/1.72.0")
        if self.options.with_qt:
            self.requires("qt/6.10.2")
        if self.options.with_openjpeg:
            self.requires("openjpeg/2.5.3")
        if self.options.with_lcms:
            self.requires("lcms/[>=2.16 <3]")
        if self.options.with_libjpeg == "libjpeg-turbo":
            self.requires("libjpeg-turbo/3.1.1")
        elif self.options.with_libjpeg == "libjpeg":
            self.requires("libjpeg/[>=9e]")
        if self.options.with_png:
            self.requires("libpng/[>=1.6 <2]")
        if self.options.with_tiff:
            self.requires("libtiff/[>=4.6.0 <5]")
        if self.options.splash:
            self.requires("boost/[>=1.81.0 <=1.89.0]")
        elif Version(self.version).major >= 25:
            self.requires("boost/[>=1.81.0 <=1.89.0]", options={"header_only": True})
        if self.options.with_libcurl:
            self.requires("libcurl/[>=7.78.0 <9]")
        if self.options.with_zlib:
            self.requires("zlib/[>=1.2.11 <2]")

    @property
    @functools.lru_cache(1)
    def _poppler_data_datadir(self):
        poppler_data_conf = self.dependencies["poppler-data"].conf_info
        return poppler_data_conf.get("user.poppler-data:datadir", check_type=str)

    def validate(self):
        if self.options.fontconfiguration == "win32" and self.settings.os != "Windows":
            raise ConanInvalidConfiguration("'win32' option of fontconfig is only available on Windows")
        if self.options.fontconfiguration == "android" and self.settings.os != "Android":
            raise ConanInvalidConfiguration("'android' option of fontconfig is only available on Android")

        # C++ standard required
        if self.settings.get_safe("compiler.cppstd"):
            check_min_cppstd(self, self._cppstd_required)

        if self.options.with_nss:
            # FIXME: missing nss recipe
            raise ConanInvalidConfiguration("nss is not (yet) available on cci")
        if self.options.get_safe("with_glib", False) and not self.options.with_cairo:
            raise ConanInvalidConfiguration("with_glib option requires with_cairo option enabled")

        if self.settings.os == "Windows" and self.options.with_libjpeg == "libjpeg":
            raise ConanInvalidConfiguration("Build with libjpeg isn't supported on Windows (see https://gitlab.freedesktop.org/poppler/poppler/-/issues/1180)")

    def build_requirements(self):
        if self.options.get_safe("with_glib", False):
            self.tool_requires("glib/<host_version>")
        self.tool_requires("cmake/[>=3.22]")
        if not self.conf.get("tools.gnu:pkg_config", check_type=str):
            self.tool_requires("pkgconf/[>=2.2 <3]")

    def source(self):
        get(self, **self.conan_data["sources"][self.version],
                  destination=self.source_folder, strip_root=True)
        apply_conandata_patches(self)

    @property
    def _dct_decoder(self):
        if self.options.with_libjpeg:
            return "libjpeg"

        return "none"

    @property
    @functools.lru_cache(1)
    def _qt_major(self):
        return Version(self.dependencies["qt"].ref.version).major

    @property
    def _uses_qt6(self):
        return self._qt_major == "6"

    @property
    def _cppstd_required(self):
        if Version(self.version).major >= "25":
            return 20

        if self.options.with_qt and self._uses_qt6:
            return 17

        return 14

    def generate(self):
        tc = CMakeToolchain(self)
        tc.cache_variables["ENABLE_UNSTABLE_API_ABI_HEADERS"] = True
        tc.cache_variables["BUILD_GTK_TESTS"] = False
        tc.cache_variables["BUILD_QT5_TESTS"] = False
        tc.cache_variables["BUILD_QT6_TESTS"] = False
        tc.cache_variables["BUILD_CPP_TESTS"] = False
        tc.cache_variables["BUILD_MANUAL_TESTS"] = False
        tc.cache_variables["ENABLE_UTILS"] = False

        tc.cache_variables["ENABLE_CPP"] = self.options.cpp
        tc.cache_variables["ENABLE_BOOST"] = self.options.splash
        tc.cache_variables["FONT_CONFIGURATION"] = self.options.fontconfiguration
        tc.cache_variables["WITH_JPEG"] = bool(self.options.with_libjpeg)
        tc.cache_variables["WITH_PNG"] = self.options.with_png
        tc.cache_variables["ENABLE_LIBTIFF"] = self.options.with_tiff
        tc.cache_variables["ENABLE_NSS3"] = self.options.with_nss
        tc.cache_variables["WITH_Cairo"] = self.options.with_cairo
        tc.cache_variables["CAIRO_FOUND"] = self.options.with_cairo
        tc.cache_variables["ENABLE_GLIB"] = self.options.get_safe("with_glib", False)
        tc.cache_variables["WITH_GTK"] = False
        tc.cache_variables["ENABLE_GOBJECT_INTROSPECTION"] = self.options.get_safe("with_gobject_introspection", False)
        tc.cache_variables["WITH_Iconv"] = self.options.get_safe("with_libiconv", False)
        tc.cache_variables["ENABLE_ZLIB"] = self.options.with_zlib
        tc.cache_variables["ENABLE_LIBOPENJPEG"] = "openjpeg2" if self.options.with_openjpeg else "none"
        tc.cache_variables["ENABLE_LCMS"] = self.options.with_lcms
        tc.cache_variables["ENABLE_LIBCURL"] = self.options.with_libcurl

        tc.cache_variables["POPPLER_DATADIR"] = self._poppler_data_datadir.replace("\\", "/")
        tc.cache_variables["FONT_CONFIGURATION"] = self.options.fontconfiguration
        tc.cache_variables["BUILD_CPP_TESTS"] = False
        tc.cache_variables["ENABLE_GTK_DOC"] = False
        tc.cache_variables["ENABLE_QT5"] = self.options.with_qt and not self._uses_qt6
        tc.cache_variables["ENABLE_QT6"] = self.options.with_qt and self._uses_qt6

        tc.cache_variables["ENABLE_DCTDECODER"] = self._dct_decoder
        tc.cache_variables["USE_FLOAT"] = self.options.float
        tc.cache_variables["RUN_GPERF_IF_PRESENT"] = False
        if self.settings.os == "Windows":
            tc.cache_variables["ENABLE_RELOCATABLE"] = self.options.shared
        tc.cache_variables["EXTRA_WARN"] = False

        # TODO: Why?
        tc.cache_variables["RUN_GPERF_IF_PRESENT"] = False

        tc.cache_variables["ENABLE_GPGME"] = False

        vbe = VirtualBuildEnv(self)
        vbe.generate()
        if not cross_building(self):
            vre = VirtualRunEnv(self)
            vre.generate(scope="build")
        tc.generate()

        deps = CMakeDeps(self)
        deps.set_property("freetype", "cmake_file_name", "FREETYPE")
        # conan-io/conan#12600

        if self.options.fontconfiguration == "fontconfig":
            deps.set_property("fontconfig", "cmake_file_name", "FONTCONFIG")
        if self.options.with_lcms:
            deps.set_property("lcms", "cmake_file_name", "LCMS2")
        if self.options.with_cairo:
            deps.set_property("cairo", "cmake_file_name", "Cairo")
        if self.options.get_safe("with_glib", False):
            deps.set_property("glib", "cmake_file_name", "GLIB")
        if self.options.with_libcurl:
            # They set a min of 7.81, supports libcurl 8 too
            deps.set_property("libcurl", "cmake_config_version_compat", "AnyNewerVersion")

        if is_msvc(self):
            deps.set_property("libjpeg", "cmake_find_mode", "module")
            deps.set_property("libiconv", "cmake_find_mode", "module")

        deps.generate()

    def build(self):
        # Use CMake's built-in version of FindIconv.cmake to fix the build on MacOS
        rm(self, "FindIconv.cmake", os.path.join(self.source_folder, "cmake", "modules"))

        if is_apple_os(self):
            pcre_path = self.dependencies["pcre2"].package_folder
            qt_path = self.dependencies["qt"].package_folder
            self.run(f"install_name_tool -add_rpath {pcre_path}/lib {qt_path}/bin/moc", ignore_errors=True)

        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        copy(self, "COPYING*", src=self.source_folder, dst=os.path.join(self.package_folder, "licenses"))
        cmake = CMake(self)
        cmake.install()
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))

    def package_info(self):
        self.cpp_info.components["libpoppler"].libs = ["poppler"]
        self.cpp_info.components["libpoppler"].includedirs.append(os.path.join("include", "poppler"))
        if self.settings.os == "Windows":
            self.cpp_info.components["libpoppler"].system_libs = ["gdi32"]

        self.cpp_info.components["libpoppler"].requires = ["poppler-data::poppler-data", "freetype::freetype"]

        if Version(self.version).major >= 25:
            self.cpp_info.components["libpoppler"].requires.append("boost::headers")

        if self.options.fontconfiguration == "fontconfig":
            self.cpp_info.components["libpoppler"].requires.append("fontconfig::fontconfig")
        if self.options.with_openjpeg:
            self.cpp_info.components["libpoppler"].requires.append("openjpeg::openjpeg")
        if self.options.with_lcms:
            self.cpp_info.components["libpoppler"].requires.append("lcms::lcms")
        if self.options.with_libjpeg == "libjpeg-turbo":
            self.cpp_info.components["libpoppler"].requires.append("libjpeg-turbo::libjpeg-turbo")
        elif self.options.with_libjpeg == "libjpeg":
            self.cpp_info.components["libpoppler"].requires.append("libjpeg::libjpeg")
        if self.options.with_png:
            self.cpp_info.components["libpoppler"].requires.append("libpng::libpng")
        if self.options.with_nss:
            self.cpp_info.components["libpoppler"].requires.append("nss::nss")
        if self.options.with_tiff:
            self.cpp_info.components["libpoppler"].requires.append("libtiff::libtiff")
        if self.options.with_libcurl:
            self.cpp_info.components["libpoppler"].requires.append("libcurl::libcurl")
        if self.options.with_zlib:
            self.cpp_info.components["libpoppler"].requires.append("zlib::zlib")

        if self.options.with_lcms:
            self.cpp_info.components["libpoppler"].requires.append("lcms::lcms")

        if self.options.cpp:
            self.cpp_info.components["libpoppler-cpp"].libs = ["poppler-cpp"]
            self.cpp_info.components["libpoppler-cpp"].includedirs.append(os.path.join("include", "poppler", "cpp"))
            self.cpp_info.components["libpoppler-cpp"].names["pkg_config"] = "poppler-cpp"
            self.cpp_info.components["libpoppler-cpp"].requires = ["libpoppler"]
            if self.options.get_safe("with_libiconv"):
                self.cpp_info.components["libpoppler-cpp"].requires.append("libiconv::libiconv")

        if self.options.splash:
            self.cpp_info.components["libpoppler-splash"].libs = []
            self.cpp_info.components["libpoppler-splash"].names["pkg_config"] = "poppler-splash"
            self.cpp_info.components["libpoppler-splash"].requires = ["libpoppler", "boost::boost"]  # FIXME: should be boost::headers, see https://github.com/conan-io/conan-center-index/pull/2097

        if self.options.with_cairo:
            self.cpp_info.components["libpoppler-cairo"].libs = []
            self.cpp_info.components["libpoppler-cairo"].names["pkg_config"] = "poppler-cairo"
            self.cpp_info.components["libpoppler-cairo"].requires = ["libpoppler", "cairo::cairo"]
        if self.options.get_safe("with_glib"):
            self.cpp_info.components["libpoppler-glib"].libs = ["poppler-glib"]
            self.cpp_info.components["libpoppler-glib"].names["pkg_config"] = "poppler-glib"
            self.cpp_info.components["libpoppler-glib"].requires = ["libpoppler-cpp", "cairo::cairo", "glib::glib", "freetype::freetype"]
            if self.options.get_safe("with_gobject_introspection"):
                self.cpp_info.components["libpoppler-glib"].requires.append("gobject-introspection::gobject-introspection")

        if self.options.with_qt:
            qt_major = self._qt_major
            self.cpp_info.components["libpoppler-qt"].libs = [f"poppler-qt{qt_major}"]
            self.cpp_info.components["libpoppler-qt"].names["pkg_config"] = f"poppler-qt{qt_major}"
            self.cpp_info.components["libpoppler-qt"].requires = ["libpoppler", "qt::qtCore", "qt::qtGui", "qt::qtWidgets"]

        datadir = self._poppler_data_datadir
        self.output.info(f"Setting POPPLER_DATADIR env var: {datadir}")
        self.env_info.POPPLER_DATADIR = datadir
