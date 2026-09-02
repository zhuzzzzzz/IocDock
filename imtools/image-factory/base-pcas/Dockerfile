# set global args here.
ARG BASE_RELEASE_VERSION=1.0.1
ARG BASE_IMAGE=base:${BASE_RELEASE_VERSION}

# 
FROM $BASE_IMAGE

# set args here.
ARG INSTALL_MODULES="pcas caPutLog"
ARG WORK_PATH=/opt/EPICS

COPY SUPPORT/ ./SUPPORT

SHELL ["/bin/bash", "-c"]

RUN <<EOF
set -ex
apt update
apt install -y build-essential libreadline-dev python3 zip
cd $WORK_PATH/SUPPORT
./automake.sh ${INSTALL_MODULES:+"--modules=${INSTALL_MODULES}"} install
apt remove -y --purge build-essential libreadline-dev python3 zip
apt autoremove -y
apt clean
rm -rf /var/lib/apt/lists/*
EOF
