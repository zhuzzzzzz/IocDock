#!/opt/EPICS/IOC/ST-IOC/bin/linux-x86_64/ST-IOC

cd /opt/EPICS/IOC/ST-IOC/iocBoot/iocST-IOC
< envPaths

cd "${TOP}"
dbLoadDatabase "dbd/ST-IOC.dbd"
ST_IOC_registerRecordDeviceDriver pdbbase


cd /opt/EPICS/RUN/test/startup
dbLoadTemplate "db/test.substitutions"

iocInit

