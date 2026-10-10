#!/bin/sh
# Build the GB Studio 4.3.2 command-line compiler into $GBS_DIR (default /tmp/gbs-src).
# Needs: GB Studio installed in /Applications, node, git, npx.
set -e
GBS_DIR="${GBS_DIR:-/tmp/gbs-src}"
APP_ASAR="/Applications/GB Studio.app/Contents/Resources/app.asar"
rm -rf "$GBS_DIR" /tmp/gbs-asar
git clone -q --depth 1 --branch v4.3.2 https://github.com/chrismaltby/gb-studio.git "$GBS_DIR"
# The engine and GBDK come prebuilt inside the app.
npx --yes @electron/asar extract "$APP_ASAR" /tmp/gbs-asar/app
rm -rf "$GBS_DIR/appData/engine"
cp -R /tmp/gbs-asar/app/appData/engine "$GBS_DIR/appData/engine"
cp -R /tmp/gbs-asar/app/buildTools/darwin-arm64/gbdk "$GBS_DIR/buildTools/darwin-arm64/"
cd "$GBS_DIR"
rm -f .yarnrc
npx --yes @yarnpkg/cli-dist@4.4.1 install --mode=skip-build
NO_TYPE_CHECKING=1 npx --yes @yarnpkg/cli-dist@4.4.1 make:cli
# The CLI imports electron but never launches it.
printf 'electron-stub' > node_modules/electron/path.txt
echo "CLI ready: $GBS_DIR/out/cli/gb-studio-cli.js"
