# Dawvia

Official distribution repository for signed Dawvia client releases.

Client downloads will be published under this repository's **Releases**. Each
release uses its full source revision as the tag. No signed client release has
been published here yet.

## Package format

Supported packages are `dawvia-darwin-arm64.tar.gz`,
`dawvia-linux-amd64.tar.gz`, and `dawvia-linux-arm64.tar.gz`, depending on the
platforms available in that release. Each package contains:

- `dawvia`: the client executable.
- `SHA256SUMS`: the signed release revision, platform, and binary SHA256.
- `SHA256SUMS.sig`: the RSA/SHA256 signature over that checksum list.

Matching aggregate `SHA256SUMS` and `SHA256SUMS.sig` files accompany the release
assets. The Dawvia installer pins the public key, archive hash and binary hash;
installation proceeds only after verification succeeds.

`release-public.pem` contains the public release-verification key. A mirror
cannot replace the installer's trusted key. Private signing and SSH keys are
never distributed here.

## Mirrors

A compatible forge serves the exact same package at:

`<repository>/releases/download/<source-revision>/dawvia-<platform>.tar.gz`

The signed-release installer accepts a space-separated list of repository URLs
with `--release-sources`. Gitee (`https://gitee.com/dawvia/dawvia`) may be added
once matching release assets are available. Only HTTPS sources and redirects
are accepted.

Product information: https://dawvia.com
