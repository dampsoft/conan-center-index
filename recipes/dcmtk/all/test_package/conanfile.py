from conan import ConanFile
from conan.tools.build import can_run
from conan.tools.cmake import CMake, cmake_layout, CMakeToolchain, CMakeDeps
from conan.tools.env import VirtualRunEnv
import os


class TestPackageConan(ConanFile):
    settings = "os", "arch", "compiler", "build_type",

    def requirements(self):
        self.requires(self.tested_reference_str)

    def layout(self):
        cmake_layout(self)

    def generate(self):
        tc = CMakeToolchain(self)
        # dcmtk requires us to build with the same cppstd as it was built with
        tc.cache_variables["CMAKE_CXX_STANDARD"] = str(self.dependencies["dcmtk"].conf_info.get("user.dcmtk:used-cppstd"))
        tc.generate()
        deps = CMakeDeps(self)
        deps.generate()
        ve = VirtualRunEnv(self)
        ve.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if can_run(self):
            bin_path = os.path.join(self.cpp.build.bindirs[0], "test_package")
            self.run(bin_path, env="conanrun")
