"""
Copyright 2018 Oliver Smith

This file is part of pmbootstrap.

pmbootstrap is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

pmbootstrap is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with pmbootstrap.  If not, see <http://www.gnu.org/licenses/>.
"""
import pmb.helpers.run
import pmb.aportgen.core
import pmb.parse.apkindex
import pmb.parse.arch


def generate_apkbuild(args, pkgname, name, arch):
    device = "-".join(pkgname.split("-")[1:])
    carch = pmb.parse.arch.alpine_to_kernel(arch)
    content = """\
        # Kernel config based on: arch/""" + carch + """/configs/(CHANGEME!)

        pkgname=\"""" + pkgname + """\"
        pkgver=3.x.x
        pkgrel=0
        pkgdesc=\"""" + name + """ kernel fork\"
        arch=\"""" + arch + """\"
        _carch=\"""" + carch + """\"
        _flavor=\"""" + device + """\"
        url="https://kernel.org"
        license="GPL2"
        options="!strip !check !tracedeps"
        makedepends="perl sed installkernel bash gmp-dev bc linux-headers elfutils-dev"
        HOSTCC="${CC:-gcc}"
        HOSTCC="${HOSTCC#${CROSS_COMPILE}}"

        # Source
        _repository="(CHANGEME!)"
        _commit="ffffffffffffffffffffffffffffffffffffffff"
        _config="config-${_flavor}.${arch}"
        source="
            $pkgname-$_commit.tar.gz::https://github.com/LineageOS/${_repository}/archive/${_commit}.tar.gz
            $_config
            compiler-gcc6.h
            01_msm-fix-perf_trace_counters.patch
            02_gpu-msm-fix-gcc5-compile.patch
        "
        builddir="$srcdir/${_repository}-${_commit}"

        prepare() {
            default_prepare

            # gcc6 support
            cp -v "$srcdir/compiler-gcc6.h" "$builddir/include/linux/"

            # Remove -Werror from all makefiles
            find . -type f -name Makefile -print0 | \\
                xargs -0 sed -i 's/-Werror-/-W/g'
            find . -type f -name Makefile -print0 | \\
                xargs -0 sed -i 's/-Werror//g'

            # Prepare kernel config ('yes ""' for kernels lacking olddefconfig)
            cp "$srcdir"/$_config "$builddir"/.config
            yes "" | make ARCH="$_carch" HOSTCC="$HOSTCC" oldconfig
        }

        menuconfig() {
            cd "$builddir"
            make ARCH="$_carch" menuconfig
            cp .config "$startdir"/$_config
        }

        build() {
            unset LDFLAGS
            make ARCH="$_carch" CC="${CC:-gcc}" \\
                KBUILD_BUILD_VERSION="$((pkgrel + 1 ))-postmarketOS"
        }

        package() {
            # kernel.release
            install -D "$builddir/include/config/kernel.release" \\
                "$pkgdir/usr/share/kernel/$_flavor/kernel.release"

            # zImage (find the right one)
            cd "$builddir/arch/$_carch/boot"
            _target="$pkgdir/boot/vmlinuz-$_flavor"
            for _zimg in zImage-dtb Image.gz-dtb *zImage Image; do
                [ -e "$_zimg" ] || continue
                msg "zImage found: $_zimg"
                install -Dm644 "$_zimg" "$_target"
                break
            done
            if ! [ -e "$_target" ]; then
                error "Could not find zImage in $PWD!"
                return 1
            fi
        }

        sha512sums="(run 'pmbootstrap checksum """ + pkgname + """' to fill)"
        """

    # Write the file
    with open(args.work + "/aportgen/APKBUILD", "w", encoding="utf-8") as handle:
        for line in content.split("\n"):
            handle.write(line[8:].replace(" " * 4, "\t") + "\n")


def generate(args, pkgname):
    device = "-".join(pkgname.split("-")[1:])
    deviceinfo = pmb.parse.deviceinfo(args, device)

    # Copy gcc6 support header and the patches from lg-mako for now
    # (automatically finding the right patches is planned in #688)
    pmb.helpers.run.user(args, ["mkdir", "-p", args.work + "/aportgen"])
    for file in ["compiler-gcc6.h", "01_msm-fix-perf_trace_counters.patch",
                 "02_gpu-msm-fix-gcc5-compile.patch"]:
        pmb.helpers.run.user(args, ["cp", args.aports +
                                    "/device/linux-lg-mako/" + file,
                                    args.work + "/aportgen/"])

    generate_apkbuild(args, pkgname, deviceinfo["name"], deviceinfo["arch"])
