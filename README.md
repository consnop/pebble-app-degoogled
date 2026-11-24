# consnop/pebble-app-degoogled: patched Gravel pipeline

This branch holds no Gravel code, only what turns upstream Gravel releases into patched builds:

- `patches/`: the changes, as `git format-patch` files, applied in order with `git am`.
- `pipeline.env`: which upstream release line to follow.
- `.github/workflows/gravel.yml`: daily, and whenever this branch changes, it takes the newest
  release tag of [david-cant-code/pebble-app-degoogled](https://github.com/david-cant-code/pebble-app-degoogled),
  applies the patches, builds the release APK **unsigned**, and publishes it as a release here named
  `<upstream tag>-consnop-<patch id>`. Signing and the installable builds live in a separate repo
  that never runs this build.

If the patches stop applying, the run fails and opens an issue here.

## Current patches

- `0001`: the four new two-button Quick Launch combos in Gravel's watch settings, for
  [consnop/PebbleOS](https://github.com/consnop/PebbleOS) firmware.
- `0002`, `0003`, `0005`: obelix_pvt watches get firmware updates from consnop/PebbleOS releases
  (its `firmware-feed.json`), and the firmware picker offers only that build.
- `0004`: dictation is transcribed in the language picked on the watch.
- `0006`: the dev connection server listens on 127.0.0.1 only and can be started over adb, so it is
  never exposed on Wi-Fi; reach it with `adb forward tcp:9000 tcp:9000` (USB or wireless debugging).

## Changing the patches

```sh
git format-patch <upstream tag>..<branch> -o patches/
```

Scheduled workflows stop after 60 days without commits on this repo; GitHub emails before that.
