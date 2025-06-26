#! /bin/bash

script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

# remove certificates that already exist.
rm ../certs/*.crt > /dev/null 2>&1
rm ../certs/*.key > /dev/null 2>&1

common_name=`IocManager config REGISTRY_COMMON_NAME`

#
openssl req \
  -newkey rsa:4096 -nodes -sha256 -keyout ../certs/registry.key \
  -addext "subjectAltName = DNS:${common_name}" \
  -x509 -days 365 -out ../certs/registry.crt << EOF 
CN
Guangdong
Shenzhen
IASF
ControlSystem
$common_name
.
EOF

openssl x509 -in ../certs/registry.crt -text -noout

# To trust that certificate
# Copy "registry.crt" to /etc/docker/certs.d/myregistrydomain:5000/ca.crt on every Docker host.

# Docker still complains about the certificate when using authentication?
# $ cp certs/domain.crt /usr/local/share/ca-certificates/myregistrydomain.crt
# $ update-ca-certificates
# https://distribution.github.io/distribution/about/insecure/
