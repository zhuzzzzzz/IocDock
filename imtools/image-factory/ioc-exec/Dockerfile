# make configuration for base image
ARG BASE_IMAGE=base:beta-0.2.2

# 
FROM $BASE_IMAGE

# make other configurations here
ARG WORK_PATH=/opt/EPICS


# install IOC modules.
COPY SUPPORT/ ./SUPPORT
RUN cd $WORK_PATH/SUPPORT; ./automake.sh install

# generate IOC executable files.
COPY IOC/ ./IOC
RUN . ~/.bash_aliases; cd $WORK_PATH/IOC/ioc-tools; ./ioc-generator.py






