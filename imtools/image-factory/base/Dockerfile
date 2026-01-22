#
FROM ubuntu:24.04

# set args here.
ARG BASE=base-7.0.8.1
ARG EPICS_HOST_ARCH=linux-x86_64
ARG WORK_PATH=/opt/EPICS
ARG BASE_PATH=${WORK_PATH}/${BASE}

#
WORKDIR $WORK_PATH
ADD ${BASE}.tar.gz .

SHELL ["/bin/bash", "-c"]

# install packages and build EPICS base. 
# build-essential needed to execute make.
# libreadline-dev needed by epics-base make.
# re2c needed by seq.
# for development:
# run "apt install -y build-essential perl libreadline-dev libreadline8 libtirpc-dev re2c iproute2 iputils-ping python3 vim-tiny"
# for deploy:
# add "apt autoremove -y" after epics-base make
RUN <<EOF
set -ex
echo "Types: deb
URIs: http://mirrors.tuna.tsinghua.edu.cn/ubuntu/
Suites: noble noble-updates noble-backports noble-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg" | tee /etc/apt/sources.list.d/tuna.sources
rm /etc/apt/sources.list.d/ubuntu.sources
apt update
apt install -y build-essential perl libreadline-dev libreadline8 libncurses6 libtirpc-dev re2c iproute2 iputils-ping vim-tiny
echo "set nocompatible\nset backspace=indent,eol,start\n" > /root/.vimrc
mv ./${BASE}/ ./base-src/
cd base-src
echo -e "\nINSTALL_LOCATION=${BASE_PATH}\n" >> ./configure/CONFIG_SITE
cat ./configure/CONFIG_SITE
make
cd ..
rm -rf base-src
apt remove -y --purge build-essential libreadline-dev
apt autoremove -y
apt clean
rm -rf /var/lib/apt/lists/*
EOF

# set environment variables.
ENV USER=root
ENV EPICS_BASE=${WORK_PATH}/${BASE}
ENV EPICS_HOST_ARCH=${EPICS_HOST_ARCH}
ENV PATH=${PATH}:${EPICS_BASE}/bin/${EPICS_HOST_ARCH}

#
CMD ["sleep", "infinity"]