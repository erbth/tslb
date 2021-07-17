  * meson


  * tclm?

  * systemd config

  * grub for wrong arch - and disable stripping for modules...

  * re-enable kernel

  * grub mkfont

  * remove vim dependency on perl

  * remove systemd dependency on dbus


  * evtl. investigate / report readelf .interp truncated bug...


  * [ ] packages incl. TPM2

  * [ ] multiple nodes per host and max num threads.

  * [ ] licenses

  * [ ] man / info update trigger

  * [ ] rtc, ... - see in general what LFS configures.

  * firmware, microcode, ...


Packages
---

  * grub: had to disable libfreetype as it's not available as package yet.

  * systemd: man depends on xsltproc?

  * dbus: libsm / x11

  * maybe run test suites of basic packages.

  * infer cdeps from rdeps

  * maybe use iana-etc from mic92?
