  * tsl-graphical

    - background image

  * look where size comes from


  * find packages that have no successful build


  * backup

  * remove old versions from collecting repo; incl. those of packages that do
    not exist anymore

  * create index

  * delete old snapshots

  * delete old rootfs images and save current ones

  * complete rebuild

  * backup


  * test flops on vm and host, and maybe on yeesha


  * evtl. investigate / report readelf .interp truncated bug...


Packages
---

  * maybe enable -dev dependencies and perform full rebuild; having digests on
    packages and being able to compare them in advance would be cool.

  * maybe run test suites of basic packages.

  * infer cdeps from rdeps

  * maybe use iana-etc from mic92?

  * maybe: grub: freetype and DejaVu font for starfield theme


Low priority
---

  * upstream fetching: github tags vs. real releases (see e.g. intel
    media-driver)

  * [ ] set some systemd default ntp servers

  * [ ] rtc, ... - see in general what LFS configures.

  * somehow remove dependencies on grub in tsl-basic and basic_tools / make
    efibootmgr update automatically / copy kernel stubs

  * [ ] licenses (also files taken from lfs etc. added in adapt; e.g. 'computer
    instructions' in blfs are subject to a MIT license); also: xorg and many
    other  dependencies come from blfs, make sure to acknowledge/appreciate that
    somewhere.; and patent issues with ffmpeg (hevc, [m]jpeg2000?) before
    distributing anything with any broader reach [as of now rather unlikely]

  * microcode

Ideas
---

  * maybe even better systemd unit handling (don't disable units during upgrade,
    stopping on change when it will not be in a new package (stopping/disabling
    in a trigger, but execstop won't be available there so implement kill
    fallback or similar), maybe cleaning notes of enabled/disabled services
    after each tpm2 run (also a design question), start unit during upgrade when
    disabled-preset was removed); maybe move to a script like deb-systemd-helper

  * maybe add a trigger to require system reboot by writing that information to
    a file

  * maybe add a facility to set systemd units to defined states after an
    upgrade/installation to the tsl-... packages. maybe this could be done
    through a trigger.

  * Libraries and other 'cdeps' can come indirectly from 'basic_build_tools'.
    These indirect cdeps will not be updated for a package's build, as the tslb
    does only look at the directly specified packages (basic_build_tools). This
    can be solved by recompiling the entire system multiple times or by
    employing a stricter order (+maybe recompiling the system less times); for
    now I stick with recompiling...

  * Rootfs images with additional packages may be chosen, therefore not
    revealing additional cdeps (because they are simply installed in the image).
    This would make imposing a stricter cdep-order among packages harder.
    However it has almost never been an issue so far (maybe because stick to a
    looser order for now...)
