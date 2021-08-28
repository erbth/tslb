  * unstable glib etc. (second or third component uneven)

  * dunst (include if < 5mib or something)

  * alsa / pulse configuration


  * gtk+/gtkmm

    - rustc and cargo

    - librsvg

  * intel_gpu_top

  * look where size comes from

  * tsl-graphical


  * find packages that have no successful build

  * remove old versions from collecting repo

  * create index

  * delete old snapshots

  * delete old rootfs images and save current ones

  * complete rebuild


  * maybe try wayland

  * test flops on vm and host, and maybe on yeesha


  * evtl. investigate / report readelf .interp truncated bug...

  * upstream fetching: github tags vs. real releases (see e.g. intel
    media-driver)


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
