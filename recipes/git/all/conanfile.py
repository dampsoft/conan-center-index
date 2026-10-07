from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.files import get
from conan.tools.gnu import Autotools, AutotoolsToolchain
from conan.tools.layout import basic_layout

required_conan_version = '>2.0'


class GitConan(ConanFile):
    name = 'git'
    license = 'GPL-2.0'
    url = 'https://github.com/dampsoft/conan-center-index'
    homepage = 'https://git-scm.com/'
    topics = 'vcs'

    package_type = 'application'
    settings = 'os', 'arch', 'compiler', 'build_type'
    options = {'prefix': ['ANY'], 'optimizations': ['profile', 'profile-fast', None]}
    default_options = {'prefix': '/', 'optimizations': None}

    def layout(self):
        basic_layout(self)
        self.folders.build = self.folders.source

    def configure(self):
        if self.options.optimizations != None and self.settings.compiler != 'gcc':
            raise ConanInvalidConfiguration("Building with optimizations is only supported when using GCC")


    def source(self):
        get(self, **self.conan_data['sources'][self.version], strip_root=True)

    def generate(self):
        tc = AutotoolsToolchain(self, prefix=self.options.prefix)
        tc.generate()

    @property
    def args(self):
        return [
            'NO_RUST=1',
            'RUNTIME_PREFIX=YesPlease',
            'gitexecdir=libexec/git-core',
            'template_dir=share/git-core/templates',
        ]


    def build(self):
        at = Autotools(self)
        at.configure()
        optimizations = self.options.optimizations
        # Git's Rust components are optional and require Cargo, which is not part of the build environment.
        if optimizations == None:
            at.make(args=self.args)
        else:
            at.make(str(optimizations), args=self.args)

    def package(self):
        at = Autotools(self)
        args = self.args
        if self.options.optimizations != None:
            args.append('PROFILE=USE')
        at.install(args=args)
