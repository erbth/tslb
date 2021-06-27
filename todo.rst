  * [ ] rdeps for maintainer scripts, also pre-deps.

  * [ ] ldconfig in configure scripts (or similar; would actually be a candidate
        for a trigger...)

  * [ ] glibc: remove /etc/ld.so.cache and run ldconfig in configure script...

  * [ ] enable new perl

  * [ ] enable gettext rdeps

  * [ ] enable vim rdeps

  * [ ] packages incl. TPM2

  * [ ] multiple nodes per host and max num threads.

  * [ ] licenses

  * [ ] tpm2 and config files

  * [ ] compile python code


Packages
---

  * shadow: configure script: pwconv / grpconv

  * bash: configure/unconfigure script for /bin/sh

  * grub: had to disable libfreetype as it's not available as package yet.

  * systemd: man depends on xsltproc?

  * dbus: libsm / x11

  * maybe run test suites of basic packages.

  * infer cdeps from rdeps
