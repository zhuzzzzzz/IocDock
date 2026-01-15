# set global args here.
ARG BASE_RELEASE_VERSION=1.0.0
ARG BASE_IMAGE=base:${BASE_RELEASE_VERSION}

# 
FROM $BASE_IMAGE

# set args here.
ARG INSTALL_MODULES=""
# ARG INSTALL_MODULES_SUPPORT_OPTIONS=${INSTALL_MODULES:+"--modules=seq ${INSTALL_MODULES}"}
# ARG INSTALL_MODULES_IOC_OPTIONS=${INSTALL_MODULES:+"--modules ${INSTALL_MODULES}"}
ARG WORK_PATH=/opt/EPICS

COPY SUPPORT/ ./SUPPORT
COPY IOC/ ./IOC

SHELL ["/bin/bash", "-c"]

# install IOC modules and generate IOC executable files.
RUN <<EOF
set -ex
apt update
apt install -y build-essential libreadline-dev python3 zip
cd $WORK_PATH/SUPPORT
./automake.sh ${INSTALL_MODULES:+"--modules=seq ${INSTALL_MODULES}"} install
cd $WORK_PATH/IOC/ioc-tools
./ioc-generator.py --with-seq ${INSTALL_MODULES:+"--modules ${INSTALL_MODULES}"}
apt remove -y --purge build-essential libreadline-dev python3 zip
apt autoremove -y
apt clean
rm -rf /var/lib/apt/lists/*
EOF







