#!/bin/bash

# ./setup-certs.sh 
# ./setup-certs.sh os-level

set -e

common_name=`IocManager config REGISTRY_COMMON_NAME`

sudo mkdir -p /etc/docker/certs.d/${common_name}/
sudo cp ./certs/registry.crt /etc/docker/certs.d/${common_name}/


if [[ "$1" != "os-level" ]];then
  exit 0
fi

# trust the certificate at OS level.
. /etc/os-release
DISTRO="${ID,,}"  # lower-case
case "${DISTRO}" in
  ubuntu|debian)
    mkdir -p /usr/local/share/ca-certificates/
    sudo cp ./certs/registry.crt /usr/local/share/ca-certificates/${common_name}.crt
    sudo update-ca-certificates --fresh
    ;;
  centos|rhel|ol)
    sudo cp certs/domain.crt /etc/pki/ca-trust/source/anchors/myregistrydomain.com.crt
    sudo update-ca-trust
    ;;
  *)
    echo "Unsupported OS: ${DISTRO}" >&2
    exit 1 
    ;;
esac


