  * rebuild after implementing correct hard link handling in split files

  * test flops on vm and host, and maybe on yeesha


  * evtl. investigate / report readelf .interp truncated bug...


Packages
---

  * systemd: man depends on xsltproc?

  * dbus: libsm / x11 -> remember that systemd depends on dbus and should be
    usable without x11

  * maybe run test suites of basic packages.

  * infer cdeps from rdeps; maybe: cdeps -> -dev package deps (how often will
    this be needed in practice?)

  * maybe use iana-etc from mic92?


Low priority
---

  * [ ] set some systemd default ntp servers

  * [ ] man / info update trigger and mandb

  * [ ] rtc, ... - see in general what LFS configures.

  * somehow remove dependencies on grub in tsl-basic and basic_tools / make
    efibootmgr update automatically / copy kernel stubs

  * [ ] licenses (also files taken from lfs etc. added in adapt; e.g. 'computer
    instructions' in blfs are subject to a MIT license)

  * microcode
