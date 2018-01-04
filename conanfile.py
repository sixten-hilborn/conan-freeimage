#!/usr/bin/env python
# -*- coding: utf-8 -*-

from conans import ConanFile, CMake, AutoToolsBuildEnvironment, tools
import os
import shutil
from os import path


class FreeImageConan(ConanFile):
    name = "freeimage"
    version = "3.17.0"
    url = "https://github.com/sixten-hilborn/conan-freeimage"
    description = "Open source image loading library"
    
    # Indicates License type of the packaged library
    license = "FIPL(http://freeimage.sourceforge.net/freeimage-license.txt)", "GPLv2", "GPLv3"
    
    # Packages the license for the conanfile.py
    exports = ["LICENSE.md"]
    
    # Remove following lines if the target lib does not use cmake.
    exports_sources = ["CMakeLists.txt", "patches/*"]
    generators = "cmake" 
    
    # Options may need to change depending on the packaged library. 
    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared"          : [True, False],
        "use_cxx_wrapper" : [True, False],

        # if set, build library without "version number" (eg.: not generate libfreeimage-3-17.0.so)
        "no_soname"       : [True, False]
    }
    default_options = (
        "shared=False",
        "use_cxx_wrapper=True",
        "no_soname=False"
    )

    # Custom attributes for Bincrafters recipe conventions
    source_subfolder = "source_subfolder"
    build_subfolder = "build_subfolder"

    short_paths = True


    def configure(self):
        if self.settings.os == "Android":
            self.options.no_soname = True

        if self.is_cmake_build():
            self.options.use_cxx_wrapper = False


    def source(self):
        source_url = "http://downloads.sourceforge.net/project/freeimage"
        tools.get(
            "{0}/Source%20Distribution/{1}/FreeImage{2}.zip".format(source_url, self.version, self.version.replace('.', '')),
            sha256='fbfc65e39b3d4e2cb108c4ffa8c41fd02c07d4d436c594fff8dab1a6d5297f89')

        #Rename to "source_subfolder" is a convention to simplify later steps
        os.rename("FreeImage", self.source_subfolder)

        self.apply_patches()


    def build(self):
        if self.is_cmake_build():
            self.build_cmake()
        else:
            self.build_make()

    def build_cmake(self):
        cmake = CMake(self)
        cmake.configure(build_folder=self.build_subfolder, source_folder=self.source_subfolder)
        cmake.build()

    def build_make(self):
        with tools.environment_append(self.make_env()):
            self.make_and_install()

    def is_cmake_build(self):
        return self.settings.compiler in ["Visual Studio", "apple-clang"]

    def make_and_install(self):
        options= "" if not self.options.use_cxx_wrapper else "-f Makefile.fip"

        make_cmd = "make %s" % (options)

        self.print_and_run(make_cmd               , cwd=self.source_subfolder)
        self.print_and_run(make_cmd + " install"  , cwd=self.source_subfolder)


    def package(self):
        self.copy(pattern="LICENSE")
        if not self.is_cmake_build():
            self.output.info("files already installed in build step")
            return

        include_dir = path.join(self.source_subfolder, 'Source')
        self.copy("FreeImage.h", dst="include", src=include_dir)
        self.copy("*.lib", dst="lib", keep_path=False)
        self.copy("*.a", dst="lib", keep_path=False)
        self.copy("*.so*", dst="lib", keep_path=False)
        self.copy("*.dylib", dst="lib", keep_path=False)
        self.copy("*.dll", dst="bin", keep_path=False)


    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)
        if not self.options.shared:
            self.cpp_info.defines.append("FREEIMAGE_LIB")


    ################################ Helpers ######################################


    def print_and_run(self, cmd, **kw):
        cwd_ = "[%s] " % kw.get('cwd') if 'cwd' in kw else ''

        self.output.info(cwd_ + str(cmd))
        self.run(cmd, **kw)

    def make_env(self):
        env_build = AutoToolsBuildEnvironment(self)

        env = env_build.vars

        # AutoToolsBuildEnvironment sets CFLAGS and CXXFLAGS, so the default value
        # on the makefile is overwriten. So, we set here the default values again
        env["CFLAGS"] += " -O3 -fPIC -fexceptions -fvisibility=hidden"
        env["CXXFLAGS"] += " -O3 -fPIC -fexceptions -fvisibility=hidden -Wno-ctor-dtor-privacy"

        if self.options.shared: #valid only for modified makefiles
            env["BUILD_SHARED"] = "1"
        if self.settings.os == "Android":
            env["NO_SWAB"] = "1"
            env["ANDROID"] = "1"

            if not os.environ.get('ANDROID_NDK_HOME'):
                env['ANDROID_NDK_HOME'] = self.get_ndk_home()

        if self.options.no_soname:
            env["NO_SONAME"] = "1"

        if not hasattr(self, 'package_folder'):
            self.package_folder = "dist"

        env["DESTDIR"]    = self.package_folder
        env["INCDIR"]     = path.join(self.package_folder, "include")
        env["INSTALLDIR"] = path.join(self.package_folder, "lib")

        return env

    def get_ndk_home(self):
        android_toolchain_opt = self.options["android-toolchain"]
        android_ndk_info = self.deps_cpp_info["android-ndk"]
        if android_toolchain_opt and android_toolchain_opt.ndk_path:
            return android_toolchain_opt.ndk_path
        elif android_ndk_info:
            return android_ndk_info.rootpath

        self.output.warn("Could not find ndk home path")

        return None

    def apply_patches(self):
        self.output.info("Applying patches")

        #Copy "patch" files
        shutil.copy('CMakeLists.txt', self.source_subfolder)
        self.copy_tree("patches", self.source_subfolder)

        self.patch_android_swab_issues()
        self.patch_android_neon_issues()

        if self.is_cmake_build():
            self.patch_cmake()
        if self.settings.compiler == "Visual Studio":
            self.patch_visual_studio()

    def patch_android_swab_issues(self):
        librawlite = path.join(self.source_subfolder, "Source", "LibRawLite")
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
        libwebp_src = path.join(self.source_subfolder, "Source", "LibWebP", "src")
        rm_neon_files = [   path.join(libwebp_src, "dsp", "dsp.h") ]
        for f in rm_neon_files:
            self.output.info("patching file '%s'" % f)
            tools.replace_in_file(f, "#define WEBP_ANDROID_NEON", "")

    def patch_cmake(self):
        tools.replace_in_file(path.join(self.source_subfolder, 'Source/FreeImage/Plugin.cpp'), 's_plugins->AddNode(InitWEBP);', '')
        tools.replace_in_file(path.join(self.source_subfolder, 'Source/FreeImage/Plugin.cpp'), 's_plugins->AddNode(InitJXR);', '')

    def patch_visual_studio(self):
        # snprintf was added in VS2015
        if self.settings.compiler.version >= 14:
            tools.replace_in_file(path.join(self.source_subfolder, 'Source/LibRawLite/internal/defines.h'), '#define snprintf _snprintf', '')
            tools.replace_in_file(path.join(self.source_subfolder, 'Source/ZLib/gzguts.h'), '#  define snprintf _snprintf', '')
            tools.replace_in_file(path.join(self.source_subfolder, 'Source/LibTIFF4/tif_config.h'), '#define snprintf _snprintf', '')

    def copy_tree(self, src_root, dst_root):
        for root, dirs, files in os.walk(src_root):
            for d in dirs:
                dst_dir = path.join(dst_root, d)
                if not path.exists(dst_dir):
                    os.mkdir(dst_dir)

                self.copy_tree(path.join(root, d), dst_dir)

            for f in files:
                shutil.copyfile(path.join(root, f), path.join(dst_root, f))

            break
