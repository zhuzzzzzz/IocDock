#!/bin/bash

script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

# set insecure-registries.
echo '{
    "registry-mirrors": ["https://dockerproxy.com",
                         "https://hub-mirror.c.163.com",
                         "https://mirror.baidubce.com",
                         "https://ccr.ccs.tencentyun.com"],
    "insecure-registries": ["https://image.dals",
    			    "https://127.0.0.1"]
}' > /etc/docker/daemon.json
if [ $? -eq 0 ]; then
    echo Restarting docker daemom.
    systemctl restart docker
else
    echo "Fail to set daemon.json for docker!"
    exit 1
fi


set -e


# set host DNS entry.
echo Set \"/etc/hosts\".
REGISTRY_IP="192.168.20.253" # Should set this variable the actual ip that the server uses.
REGISTRY_NAME="image.dals"

new_line="$REGISTRY_IP\t$REGISTRY_NAME"

file="/etc/hosts"
if [ ! -f "$file" ]; then  
    touch "$file"  
fi
#
echo -n \# >> /etc/hosts.old
date >> /etc/hosts.old
echo \# backup of /etc/hosts >> /etc/hosts.old
cat $file >> /etc/hosts.old
echo >> /etc/hosts.old
#
echo -e "$new_line" >> hosts
cat /etc/hosts.old >> hosts
mv hosts "$file"

if [ ! "$1" == 'manager' ]; then
	echo Finished.
	exit
fi

# check certificates and registry dir(for docker-manager).
echo Set certificates and prepare for docker compose up.
CERT_DIR="certs"
CERT_PREFIX="dals_domain"
REGISTRY_DIR="registry"

if [ ! -f "$CERT_DIR/$CERT_PREFIX.crt" -o ! -f "$CERT_DIR/$CERT_PREFIX.key" ]; then
	cd $CERT_DIR
	./make-certs.sh
	cd $script_dir
fi
if [ ! -d "$REGISTRY_DIR" ]; then
	mkdir $REGISTRY_DIR
fi

echo Finished. You can start docker-manager now.
