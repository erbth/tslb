  * network tools (tcpdump, nslookup/dig, openssh-server, ...)

  * systemd services (disable for nfs-utils (does that on its own), openssh-server)


  * create tsl-basic


  * check if all required packages are enabled


  * [ ] man / info update trigger

  * [ ] rtc, ... - see in general what LFS configures.

  * firmware, microcode, ...

  * [ ] packages incl. TPM2

  * [ ] licenses (also files taken from lfs etc. added in adapt)

  * evtl. investigate / report readelf .interp truncated bug...

  * systemd ntp servers

  * try sse


Packages
---

  * systemd: man depends on xsltproc?

  * dbus: libsm / x11 -> remember that systemd depends on dbus and should be
    usable without x11

  * maybe run test suites of basic packages.

  * infer cdeps from rdeps; cdeps -> -dev package deps

  * maybe use iana-etc from mic92?
