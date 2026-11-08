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
  [consnop/PebbleOS](https://github.com/consnop/PebbleOS) firmware. Developed on the `combos` branch.

## Changing the patches

```sh
git format-patch <upstream tag>..<branch> -o patches/
```

Scheduled workflows stop after 60 days without commits on this repo; GitHub emails before that.
