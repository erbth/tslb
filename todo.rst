  * better systemd unit handling; initially enable new units on upgrade (get
    some inspiration from deb-systemd-helper); socket activation and install

  * util-linux: fstrim.timer

  * uuidd

  * recompile e2fsprogs and see if systemd units are handled correctly

  * [ ] mandb / texinfo index update trigger

  * test flops on vm and host, and maybe on yeesha


  * delete old snapshots

  * delete old rootfs images


  * evtl. investigate / report readelf .interp truncated bug...

  * upstream fetching: github tags vs. real releases (see e.g. intel
    media-driver)


Packages
---

  * maybe enable -dev dependencies and perform full rebuild; having digests on
    packages and being able to compare them in advance would be cool.

  * systemd: man depends on xsltproc?

  * maybe run test suites of basic packages.

  * infer cdeps from rdeps

  * maybe use iana-etc from mic92?

  * maybe: grub: freetype and DejaVu font for starfield theme


Low priority
---

  * [ ] set some systemd default ntp servers

  * [ ] rtc, ... - see in general what LFS configures.

  * somehow remove dependencies on grub in tsl-basic and basic_tools / make
    efibootmgr update automatically / copy kernel stubs

  * [ ] licenses (also files taken from lfs etc. added in adapt; e.g. 'computer
    instructions' in blfs are subject to a MIT license); also: xorg dependencies
    come from blfs, make sure to acknowledge that somewhere.

  * microcode

Ideas
---

  * maybe even better systemd unit handling (don't disable units during upgrade,
    stopping on change when it will not be in a new package (stopping/disabling
    in a trigger, but execstop won't be available there so implement kill
    fallback or similar), cleaning notes of disabled services after each tpm2
    run, start unit during upgrade when disabled-preset was removed); maybe move
    to a script like deb-systemd-helper

  * maybe add a trigger to require system reboot by writing that information to
    a file
