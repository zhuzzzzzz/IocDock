#!/bin/bash

set -ex

if [ -f /etc/os-release ]; then
    . /etc/os-release
    case $ID in
        ubuntu)
            ;;
        centos)
            ;;
        *)
            echo "Failed. Only support for ubuntu and centOS now."
            exit 1
            ;;
    esac
else
    echo "Failed. Can't check OS information."
    exit 1
fi

# install docker and python-packeges
case $ID in
    ubuntu)
        # Add Docker's official GPG key:
        apt-get update
        apt-get install ca-certificates curl
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
        chmod a+r /etc/apt/keyrings/docker.asc
        # Add the repository to Apt sources:
        echo \
  	      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
          $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
          sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        apt-get update
        #
        sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        #
        groupadd docker
        usermod -aG docker $USER
        newgrp docker
        #
        apt install python3-pip
        apt install python3-docker python3-tabulate
        ;;
    centos)
        #
        dnf -y install dnf-plugins-core
        dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        dnf install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        systemctl enable --now docker
        #
        groupadd docker
        usermod -aG docker $USER
        newgrp docker
        #
        pip3 install docker tabulate
        ;;
    *)
        echo "Failed. Only support for ubuntu and centOS now."
	    exit 1
        ;;
esac






