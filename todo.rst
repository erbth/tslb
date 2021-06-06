  * [ ] packages incl. TPM2

  * [ ] multiple nodes per host and max num threads.

  * [ ] Version numbers of grub and openssl

  * [ ] licenses

  * [ ] delete scratch spaces of source packages when the entire source package
        is deleted (maybe just delete all versions first).


Packages
---

  * shadow: configure script: pwconv / grpconv

  * bash: configure/unconfigure script for /bin/sh

  * grub: had to disable libfreetype as it's not available as package yet.

  * systemd: man depends on xsltproc?

  * dbus: libsm / x11

  * maybe run test suites of basic packages.

  * infer cdeps from rdeps
