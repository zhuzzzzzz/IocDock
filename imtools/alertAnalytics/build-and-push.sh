#!/bin/bash
image_name="alert-analytics"
release_version=0.1.1
build_dir="$(dirname "$(readlink -f "$0")")"
source "$build_dir/../common-build-push.sh"
