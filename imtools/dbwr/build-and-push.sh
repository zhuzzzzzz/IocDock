#!/bin/bash
image_name="dbwr"
release_version=0.0.1
build_dir="$(dirname "$(readlink -f "$0")")"
source "$build_dir/../common-build-push.sh"
