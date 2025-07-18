#!/bin/sh

set -ex

echo "$@"

export HOSTNAME=$(cat /etc/hostname)

set -- /bin/prometheus "$@"

exec "$@"
