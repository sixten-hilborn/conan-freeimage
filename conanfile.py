from conans import ConanFile, CMake, tools
import os
from os import path
from shutil import copy, copyfile


class FreeImageConan(ConanFile):
    name = "freeimage"
    version = "3.17.0"
    license = "FIPL(http://freeimage.sourceforge.net/freeimage-license.txt)", "GPLv2", "GPLv3"
    description = "Open source image loading library"

    url = "https://github.com/sixten-hilborn/freeimage-conan"
    generators = "cmake"
    settings = "os", "compiler", "arch", "build_type"

    options = {
        "shared"          : [True, False],
        "use_cxx_wrapper" : [True, False]
    }
    default_options = (
        "shared=False",
        "use_cxx_wrapper=True"
    )

    exports = ("CMakeLists.txt", "patches/*")

    # Downloading from sourceforge
    REPO = "http://downloads.sourceforge.net/project/freeimage/"
    DOWNLOAD_LINK = REPO + "Source%20Distribution/3.17.0/FreeImage3170.zip"
    # Folder inside the zip
    UNZIPPED_DIR = "FreeImage"
    FILE_SHA = 'fbfc65e39b3d4e2cb108c4ffa8c41fd02c07d4d436c594fff8dab1a6d5297f89'

    def configure(self):
        self.options.use_cxx_wrapper = False

    def source(self):
        zip_name = self.name + ".zip"

        tools.download(self.DOWNLOAD_LINK, zip_name)
        tools.check_sha256(zip_name, self.FILE_SHA)
        tools.unzip(zip_name)
        os.unlink(zip_name)

    def build(self):
        self.apply_patches()
        cmake = CMake(self)
        cmake.definitions['BUILD_SHARED_LIBS'] = self.options.shared
        cmake.configure(build_dir=self.UNZIPPED_DIR, source_dir='.')
        cmake.build()

    def package(self):
        include_dir = path.join(self.UNZIPPED_DIR, 'Source')
        self.copy("FreeImage.h", dst="include", src=include_dir)
        self.copy("*.lib", dst="lib", src=self.UNZIPPED_DIR, keep_path=False)
        self.copy("*.a", dst="lib", src=self.UNZIPPED_DIR, keep_path=False)
        self.copy("*.so", dst="lib", src=self.UNZIPPED_DIR, keep_path=False)
        self.copy("*.dylib", dst="lib", src=self.UNZIPPED_DIR, keep_path=False)
        self.copy("*.dll", dst="bin", src=self.UNZIPPED_DIR, keep_path=False)

    def package_info(self):
        self.cpp_info.libs = ["FreeImage"]

        if self.options.use_cxx_wrapper:
            self.cpp_info.libs.append("freeimageplus")
        if not self.options.shared:
            self.cpp_info.defines.append("FREEIMAGE_LIB")

    ################################ Helpers ######################################

    def apply_patches(self):
        self.output.info("Applying patches")

        #Copy "patch" files
        copy('CMakeLists.txt', self.UNZIPPED_DIR)
        self.copy_tree("patches", self.UNZIPPED_DIR)

        self.patch_android_swab_issues()
        self.patch_android_neon_issues()

        # Don't use webp/jxr with cmake build
        tools.replace_in_file(path.join(self.UNZIPPED_DIR, 'Source/FreeImage/Plugin.cpp'), 's_plugins->AddNode(InitWEBP);', '')
        tools.replace_in_file(path.join(self.UNZIPPED_DIR, 'Source/FreeImage/Plugin.cpp'), 's_plugins->AddNode(InitJXR);', '')
        # snprintf was added in VS2015
        if self.settings.compiler == "Visual Studio" and int(str(self.settings.compiler.version)) >= 14:
            tools.replace_in_file(path.join(self.UNZIPPED_DIR, 'Source/LibRawLite/internal/defines.h'), '#define snprintf _snprintf', '')
            tools.replace_in_file(path.join(self.UNZIPPED_DIR, 'Source/ZLib/gzguts.h'), '#  define snprintf _snprintf', '')
            tools.replace_in_file(path.join(self.UNZIPPED_DIR, 'Source/LibTIFF4/tif_config.h'), '#define snprintf _snprintf', '')

    def patch_android_swab_issues(self):
        librawlite = path.join(self.UNZIPPED_DIR, "Source", "LibRawLite")
        missing_swab_files = [
            path.join(librawlite, "dcraw", "dcraw.c"),
            path.join(librawlite, "internal", "defines.h")
        ]
        replaced_include = '\n'.join(('#include <unistd.h>', '#include "swab.h"'))

        for f in missing_swab_files:
            self.output.info("patching file '%s'" % f)
            tools.replace_in_file(f, "#include <unistd.h>", replaced_include)

    def patch_android_neon_issues(self):
        # avoid using neon
        libwebp_src = path.join(self.UNZIPPED_DIR, "Source", "LibWebP", "src")
        rm_neon_files = [   path.join(libwebp_src, "dsp", "dsp.h") ]
        for f in rm_neon_files:
            self.output.info("patching file '%s'" % f)
            tools.replace_in_file(f, "#define WEBP_ANDROID_NEON", "")

    def copy_tree(self, src_root, dst_root):
#        for p in self.patches:
#        for p in os.listdir('patches'):
        for root, dirs, files in os.walk(src_root):
            for d in dirs:
                dst_dir = path.join(dst_root, d)
                if not path.exists(dst_dir):
                    os.mkdir(dst_dir)
                    
                self.copy_tree(path.join(root, d), dst_dir)
            
            for f in files:
                copyfile(path.join(root, f), path.join(dst_root, f))

            break
