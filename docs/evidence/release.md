# Release evidence, 2026-10-11 21:01 local

Commit: 8ec3b472daadf8f031ba79cc1a6c903efee89c03

## Font files on the build machine (SHA-256)

- CabinetGrotesk-Variable.woff2: f71103771c9e32406026b6ea46c7e57cb977d5884e70d0f1beeab91ab2c7abb6
- PatrickHand-Regular.woff2: b7b42c1ffca34baa25a9990f64362e47d62cded0fb66360bd0affe2422f11ce2
- Switzer-Variable.woff2: d1bf801ffb1a6096def70a7c532255722ad87d948b13a8a586e342f7091f8ee4

## Image

- label: registry.fly.io/wiggle-outside:v8ec3b47
- digest: sha256:d39de6af74d234e92d25ca3f419e07ad68b4f0ac87852ea9369abae317930809 (from the build output)

## Deploy 2 (TC-011 round 1)

- commit: f923e03
- digest: sha256:87bfcbdcfa8370ef003baf31e98153738e79a3892cda26eabbdde4dbbb2c192c

## Deploy 3 (round 2, loader, 404/405, privacy fix)

- commit: 34011ce
- digest: sha256:aa6f8791824d1dfebc28e14225d33862e95dd3c771af1ea915d80a0dcfb644fa

## Deploy 4 (final fixes)

- commit: bb170b6
- digest: sha256:f61163bd621753c2916c343e9f6d793bf629e6bfa5ec35c81bb4ebbf99537133

## Deploy 5 (TC-012)

- commit: be812ec
- digest: sha256:6be11867c3eb720ba4cca262c405908f5933aec5826f77e3f53b284f672e220d

## Deploy 6 (capitalised items, CI Bun step)

- commit: baf7241
- digest: sha256:def0029db31ce934951a2d571b38ef7ff95a136f3ca8841589664adbdce04213
- machine version: 6
- deployed: 2026-10-11T23:07Z

## Deploy 7 (phase 2 cleanup, httpx log privacy fix)

- commit: dc04137
- digest: sha256:4436726aebeae8093e4fc8db0037b2c71b3d2d348edcc15166bc9f8bf691112b
- machine version: 7
- deployed: 2026-10-12T00:05Z
- includes the httpx log privacy fix: provider request URLs (rounded coordinates, the
  typed town) are no longer written to the logs (`main.configure_logging`, QUIET_LOGGERS)

## Published post

- <https://dev.to/moonchichiii/wiggle-outside-weather-nearby-places-and-a-little-inspiration-in-one-short-search-25cc>
- published: 2026-10-11T23:53Z
