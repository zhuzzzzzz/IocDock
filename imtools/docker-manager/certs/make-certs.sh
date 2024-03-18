#!/bin/bash

# remove certificates that already exist.
rm *.crt
rm *.key

CERT_PREFIX="dals_domain"

openssl genrsa -out $CERT_PREFIX.key 2048
#openssl req -new -x509 -key $CERT_PREFIX.key -out $CERT_PREFIX.crt -addext "subjectAltName = IP:192.168.43.182" << EOF 
openssl req -new -x509 -key $CERT_PREFIX.key -out $CERT_PREFIX.crt << EOF 
CN
Liaoning
Dalian
DALS
IT
.
.
EOF
echo 

