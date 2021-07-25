  * create tsl-basic

  * try sse

  * check if all required packages are enabled

  * firmware, microcode, ...


  * [ ] man / info update trigger and mandb

  * [ ] rtc, ... - see in general what LFS configures.

  * [ ] packages incl. TPM2

  * [ ] licenses (also files taken from lfs etc. added in adapt; e.g. 'computer
    instructions' in blfs are subject to a MIT license)

  * evtl. investigate / report readelf .interp truncated bug...

  * systemd ntp servers


Packages
---

  * systemd: man depends on xsltproc?

  * dbus: libsm / x11 -> remember that systemd depends on dbus and should be
    usable without x11

  * maybe run test suites of basic packages.

  * infer cdeps from rdeps; maybe: cdeps -> -dev package deps (how often will
    this be needed in practice?)

  * maybe use iana-etc from mic92?
