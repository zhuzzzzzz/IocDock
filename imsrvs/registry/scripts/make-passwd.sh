#!/bin/bash

docker run \
  --entrypoint htpasswd \
  m.daocloud.io/docker.io/httpd:2 \
  -Bbn admin admin > ../auth/htpasswd

if [ $? -eq 0 ]; then
    echo '"../auth/htpasswd" created.'
else
    echo 'failed to create "../auth/htpasswd".'
fi
