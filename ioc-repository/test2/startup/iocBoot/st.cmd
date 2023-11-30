#!/opt/EPICS/IOC/ST-IOC/bin/linux-x86_64/ST-IOC

cd /opt/EPICS/IOC/ST-IOC/iocBoot/iocST-IOC
< envPaths

cd "${TOP}"
dbLoadDatabase "dbd/ST-IOC.dbd"
ST_IOC_registerRecordDeviceDriver pdbbase


cd /opt/EPICS/RUN/test2/startup
dbLoadTemplate "db/test2.substitutions"
dbLoadRecords("db/status_ioc.db","IOC=test2")
dbLoadRecords("db/status_OS.db","HOST=test2:docker")

iocInit

