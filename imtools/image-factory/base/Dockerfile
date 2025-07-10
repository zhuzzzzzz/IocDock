#
FROM ubuntu:24.04

# install packages.
# build-essential needed to execute make.
# re2c needed by seq.
# other tools: vim net-tools inetutils-ping python3 
RUN apt update && apt install -y build-essential re2c vim net-tools inetutils-ping python3 zip libtirpc-dev && rm -rf /var/lib/apt/lists/*

# make configurations here
ARG BASE=base-7.0.8.1
ARG WORK_PATH=/opt/EPICS

# epics-base
WORKDIR $WORK_PATH
ADD $BASE.tar.gz .
RUN cd $BASE; make

# set environment variable(using ~/.bash_aliases)
ENV USER=root
ENV EPICS_BASE=$WORK_PATH/$BASE
COPY .bash_aliases /root/
COPY setENV.sh /root/

#
