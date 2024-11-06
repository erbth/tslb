
  * evtl. investigate / report readelf .interp truncated bug...


Packages (low priority)
---

  * maybe enable -dev dependencies and perform full rebuild; having digests on
    packages and being able to compare them in advance would be cool.

  * maybe run test suites of basic packages.

  * infer cdeps from rdeps

  * maybe use iana-etc from mic92?

  * maybe: grub: freetype and DejaVu font for starfield theme

  * maybe run grub-install on upgrade (if required...)

  * maybe don't create a systemd journal by default or only create the directory
    once, maybe treat it like a configuration file


Low priority
---

  * source package version constraints in binary packages, e.g.
    tsl-graphical -> tsl_graphical_wallpaper = s:built

  * [ ] set some systemd default ntp servers

  * [ ] rtc, ... - see in general what LFS configures.

  * [ ] licenses (also files taken from lfs etc. added in adapt; e.g. 'computer
    instructions' in blfs are subject to a MIT license); also: xorg and many
    other  dependencies come from blfs, make sure to acknowledge/appreciate that
    somewhere.; and patent issues with ffmpeg (hevc, [m]jpeg2000?) before
    distributing anything with any broader reach [as of now rather unlikely];
    and maybe ensure that all scripts added during adapt etc. that come from
    e.g.  Debian contain a notice (however the sources have to be distributed,
    anyway, and they will carry notices).

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
