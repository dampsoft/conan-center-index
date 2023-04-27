from conan import ConanFile
from conan.tools.cmake import CMake, CMakeToolchain, CMakeDeps
from conan.tools.build import cross_building
import os


class TestPackageConan(ConanFile):
    settings = "os", "arch", "compiler", "build_type"

    def generate(self):
        tc = CMakeToolchain(self)
        # dcmtk requires us to build with the same cppstd as it was built with
        tc.variables["CMAKE_CXX_STANDARD"] = self.dependencies["dcmtk"].buildenv_info.vars(self)["CXX_STANDARD"]
        tc.generate()
        deps = CMakeDeps(self)
        deps.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def test(self):
        if not cross_building(self):
            bin_path = os.path.join("bin", "test_package")
            self.run(bin_path, run_environment=True)
