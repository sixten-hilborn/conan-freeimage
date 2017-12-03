from conans import CMake, ConanFile
import os

class DefaultNameConan(ConanFile):
    name = "DefaultName"
    version = "0.1"
    settings = "os", "compiler", "arch", "build_type"
    generators = "cmake"

    def build(self):
        cmake = CMake(self)
        cmake.configure(build_dir='.')
        cmake.build()

    def imports(self):
        self.copy(pattern="*.dll", dst="bin", src="bin")
        self.copy(pattern="*.dylib", dst="bin", src="lib")
        
    def test(self):
        img_path = os.path.join(self.conanfile_directory, "test.png")
        self.run("cd bin && .%sexample %s" % (os.sep, img_path))
