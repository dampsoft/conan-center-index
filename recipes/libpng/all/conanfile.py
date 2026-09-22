from conan import ConanFile
from conan.tools.cmake import CMake, CMakeToolchain, CMakeDeps, cmake_layout
from conan.tools.files import copy, get, rm, rmdir
from conan.tools.microsoft import is_msvc
from conan.tools.scm import Version
import os
import re
import shutil
import subprocess

required_conan_version = ">=2.0"


_MACRO = re.compile(r"^(#(?:define|undef)\s+([A-Za-z_][A-Za-z0-9_]*).*)$")


class LibpngConan(ConanFile):
    name = "libpng"
    package_type = "library"
    description = "libpng is the official PNG file format reference library."
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "http://www.libpng.org"
    license = "libpng-2.0"
    topics = ("png", "graphics", "image")
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "neon": [True, "check", False],
        "msa": [True, False],
        "sse": [True, False],
        "vsx": [True, False],
        "api_prefix": ["ANY"],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "neon": True,
        "msa": True,
        "sse": True,
        "vsx": True,
        "api_prefix": "",
    }

    @property
    def _is_clang_cl(self):
        return self.settings.os == "Windows" and self.settings.compiler == "clang" and \
               self.settings.compiler.get_safe("runtime")

    @property
    def _is_macos_universal(self):
        return self.settings.os == "Macos" and "|" in str(self.settings.arch)

    @property
    def _has_neon_support(self):
        return "arm" in self.settings.arch or self._is_macos_universal

    @property
    def _has_msa_support(self):
        return "mips" in self.settings.arch

    @property
    def _has_sse_support(self):
        return self.settings.arch in ["x86", "x86_64"] or self._is_macos_universal

    @property
    def _has_vsx_support(self):
        return "ppc" in self.settings.arch

    @property
    def _neon_msa_sse_vsx_mapping(self):
        return {
            "True": "on",
            "False": "off",
            "check": "check",
        }

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC
        if not self._has_neon_support:
            del self.options.neon
        if not self._has_msa_support:
            del self.options.msa
        if not self._has_sse_support:
            del self.options.sse
        if not self._has_vsx_support:
            del self.options.vsx

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")
        self.settings.rm_safe("compiler.libcxx")
        self.settings.rm_safe("compiler.cppstd")

    def layout(self):
        cmake_layout(self, src_folder="src")

    def requirements(self):
        self.requires("zlib/[>=1.2.11 <2]")

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def generate(self):
        tc = CMakeToolchain(self)
        tc.cache_variables["PNG_TESTS"] = False
        tc.cache_variables["PNG_SHARED"] = self.options.shared
        tc.cache_variables["PNG_STATIC"] = not self.options.shared
        tc.cache_variables["PNG_DEBUG"] = self.settings.build_type == "Debug"
        tc.cache_variables["PNG_PREFIX"] = self.options.api_prefix
        tc.cache_variables["PNG_FRAMEWORK"] = False  # changed from False to True by default in PNG 1.6.41
        tc.cache_variables["PNG_TOOLS"] = False
        tc.cache_variables["CMAKE_MACOSX_BUNDLE"] = False
        if self._is_macos_universal:
            tc.blocks["apple_system"].template = tc.blocks["apple_system"].template.replace(
                'set(CMAKE_OSX_ARCHITECTURES {{ cmake_osx_architectures }} CACHE STRING "" FORCE)',
                '# CMAKE_OSX_ARCHITECTURES set per-slice by recipe'
            )
        elif self._has_neon_support:
            tc.cache_variables["PNG_ARM_NEON"] = self._neon_msa_sse_vsx_mapping[str(self.options.neon)]
        if self._has_msa_support:
            tc.cache_variables["PNG_MIPS_MSA"] = self._neon_msa_sse_vsx_mapping[str(self.options.msa)]
        if self._has_sse_support and not self._is_macos_universal:
            tc.cache_variables["PNG_INTEL_SSE"] = self._neon_msa_sse_vsx_mapping[str(self.options.sse)]
        if self._has_vsx_support:
            tc.cache_variables["PNG_POWERPC_VSX"] = self._neon_msa_sse_vsx_mapping[str(self.options.vsx)]
        
        tc.generate()
        tc = CMakeDeps(self)
        tc.generate()

    def _is_macho(self, path):
        return subprocess.run(
            ["lipo", "-archs", path], capture_output=True, text=True, check=False
        ).returncode == 0

    def _merge_config_header(self, arm_path, x86_path, output_path):
        with open(arm_path, encoding="utf-8") as arm_file:
            arm_lines = arm_file.readlines()
        with open(x86_path, encoding="utf-8") as x86_file:
            x86_lines = x86_file.readlines()

        def macros(lines):
            return {
                match.group(2): match.group(1)
                for line in lines
                if (match := _MACRO.match(line.rstrip("\n")))
            }

        arm_macros = macros(arm_lines)
        x86_macros = macros(x86_lines)
        changed = {
            name for name in arm_macros.keys() | x86_macros.keys()
            if arm_macros.get(name) != x86_macros.get(name)
        }
        if not changed:
            return False

        def without_changed_macros(lines):
            return [
                line for line in lines
                if not (match := _MACRO.match(line.rstrip("\n"))) or match.group(2) not in changed
            ]

        def configuration_shape(lines):
            return [
                line for line in without_changed_macros(lines)
                if line.strip() and not line.lstrip().startswith(("/*", "*", "*/"))
            ]

        if configuration_shape(arm_lines) != configuration_shape(x86_lines):
            return False

        merged = []
        emitted = set()
        for line in arm_lines:
            match = _MACRO.match(line.rstrip("\n"))
            if not match or match.group(2) not in changed:
                merged.append(line)
                continue
            name = match.group(2)
            if name in emitted:
                continue
            emitted.add(name)
            merged.extend([
                "#if defined(__aarch64__)\n",
                f"{arm_macros.get(name, f'#undef {name}')}\n",
                "#elif defined(__x86_64__)\n",
                f"{x86_macros.get(name, f'#undef {name}')}\n",
                "#else\n",
                "#error Unsupported macOS universal architecture\n",
                "#endif\n",
            ])

        for name in sorted(changed - emitted):
            merged.extend([
                "#if defined(__aarch64__)\n",
                f"{arm_macros.get(name, f'#undef {name}')}\n",
                "#elif defined(__x86_64__)\n",
                f"{x86_macros.get(name, f'#undef {name}')}\n",
                "#else\n",
                "#error Unsupported macOS universal architecture\n",
                "#endif\n",
            ])

        with open(output_path, "w", encoding="utf-8") as output_file:
            output_file.writelines(merged)
        return True

    def _merge_slices(self, arm_dir, x86_dir, dst_dir):
        for root, _, files in os.walk(arm_dir):
            rel_dir = os.path.relpath(root, arm_dir)
            target_dir = os.path.normpath(os.path.join(dst_dir, rel_dir))
            os.makedirs(target_dir, exist_ok=True)

            for file in files:
                arm_path = os.path.join(root, file)
                x86_path = os.path.join(x86_dir, rel_dir, file)
                dst_path = os.path.join(target_dir, file)

                if os.path.islink(arm_path):
                    target = os.readlink(arm_path)
                    if os.path.lexists(dst_path):
                        os.remove(dst_path)
                    os.symlink(target, dst_path)
                    continue

                if self._is_macho(arm_path) and os.path.exists(x86_path) and self._is_macho(x86_path):
                    self.run(f'lipo -create "{arm_path}" "{x86_path}" -output "{dst_path}"')
                    self.run(f'lipo "{dst_path}" -verify_arch arm64')
                    self.run(f'lipo "{dst_path}" -verify_arch x86_64')
                elif (file.endswith(".h") or file.endswith(".hpp")) and os.path.exists(x86_path):
                    if not self._merge_config_header(arm_path, x86_path, dst_path):
                        if dst_path != arm_path:
                            shutil.copy2(arm_path, dst_path)
                else:
                    if dst_path != arm_path:
                        shutil.copy2(arm_path, dst_path)

    def build(self):
        if self._is_macos_universal:
            slice_vars = {
                "arm64": {
                    "CMAKE_OSX_ARCHITECTURES": "arm64",
                    "PNG_ARM_NEON": self._neon_msa_sse_vsx_mapping[str(self.options.neon)],
                    "PNG_INTEL_SSE": "off",
                },
                "x86_64": {
                    "CMAKE_OSX_ARCHITECTURES": "x86_64",
                    "PNG_ARM_NEON": "off",
                    "PNG_INTEL_SSE": self._neon_msa_sse_vsx_mapping[str(self.options.sse)],
                },
            }
            for arch in ("arm64", "x86_64"):
                cmake = CMake(self)
                cmake.configure(variables=slice_vars[arch], subfolder=arch)
                cmake.build(subfolder=arch)
        else:
            cmake = CMake(self)
            cmake.configure()
            cmake.build()

    def package(self):
        copy(self, "LICENSE", src=self.source_folder, dst=os.path.join(self.package_folder, "licenses"))
        if self._is_macos_universal:
            cmake = CMake(self)
            cmake.install(subfolder="arm64")
            cmake.install(subfolder="x86_64")
            arm_pkg = os.path.join(self.package_folder, "arm64")
            x86_pkg = os.path.join(self.package_folder, "x86_64")
            self._merge_slices(arm_pkg, x86_pkg, self.package_folder)
            shutil.rmtree(arm_pkg)
            shutil.rmtree(x86_pkg)
        else:
            cmake = CMake(self)
            cmake.install()
        if self.options.shared:
            rm(self, "*[!.dll]", os.path.join(self.package_folder, "bin"))
        else:
            rmdir(self, os.path.join(self.package_folder, "bin"))
        rmdir(self, os.path.join(self.package_folder, "lib", "libpng"))
        rmdir(self, os.path.join(self.package_folder, "lib", "pkgconfig"))
        rmdir(self, os.path.join(self.package_folder, "share"))
        rm(self, "*.cmake", os.path.join(self.package_folder, "lib", "cmake", "PNG"))

    def package_info(self):
        major_min_version = f"{Version(self.version).major}{Version(self.version).minor}"

        self.cpp_info.set_property("cmake_find_mode", "both")
        self.cpp_info.set_property("cmake_file_name", "PNG")
        self.cpp_info.set_property("cmake_target_name", "PNG::PNG")
        self.cpp_info.set_property("pkg_config_name", "libpng")
        self.cpp_info.set_property("pkg_config_aliases", [f"libpng{major_min_version}"])

        prefix = "lib" if (is_msvc(self) or self._is_clang_cl) else ""
        suffix = major_min_version if self.settings.os == "Windows" else ""
        if is_msvc(self) or self._is_clang_cl:
            suffix += "_static" if not self.options.shared else ""
        suffix += "d" if self.settings.os == "Windows" and self.settings.build_type == "Debug" else ""
        self.cpp_info.libs = [f"{prefix}png{suffix}"]
        if self.settings.os in ["Linux", "Android", "FreeBSD", "SunOS", "AIX"]:
            self.cpp_info.system_libs.append("m")
