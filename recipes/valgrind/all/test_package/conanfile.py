from conan import ConanFile


class ValgrindTestConan(ConanFile):
    def build_requirements(self):
        self.tool_requires(self.tested_reference_str)

    def test(self):
        self.run("valgrind --version")
