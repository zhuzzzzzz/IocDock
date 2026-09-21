# set global args here.
ARG BASE_RELEASE_VERSION=1.0.1
ARG BASE_IMAGE=base-pcas:${BASE_RELEASE_VERSION}

# 
FROM $BASE_IMAGE

#
ARG WORK_PATH=/opt/EPICS/SUPPORT
ARG APP_VERSION=2.1.3
ARG EPICS_HOST_ARCH=linux-x86_64

#
WORKDIR $WORK_PATH
ADD ca-gateway-${APP_VERSION}.tar.gz .

SHELL ["/bin/bash", "-c"]

RUN <<EOF
set -ex
apt update
apt install -y build-essential libreadline-dev python3 zip
pcas_pkg=`ls | grep -i pcas-`
echo PCAS=$(pwd)/$pcas_pkg >> RELEASE.local
cd ca-gateway-${APP_VERSION}
make
apt remove -y --purge build-essential libreadline-dev python3 zip
apt autoremove -y
apt clean
rm -rf /var/lib/apt/lists/*
EOF

WORKDIR $WORK_PATH/ca-gateway-${APP_VERSION}/bin/${EPICS_HOST_ARCH}

ENTRYPOINT ["./gateway"]