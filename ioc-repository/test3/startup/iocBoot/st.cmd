#!/opt/EPICS/IOC/ST-IOC/bin/linux-x86_64/ST-IOC

cd /opt/EPICS/IOC/ST-IOC/iocBoot/iocST-IOC
< envPaths

cd "${TOP}"
dbLoadDatabase "dbd/ST-IOC.dbd"
ST_IOC_registerRecordDeviceDriver pdbbase

#caPutLog
asSetFilename("/opt/EPICS/RUN/test3/settings/test3.acf")
epicsEnvSet("EPICS_IOC_LOG_INET","127.0.0.1")
iocLogPrefix("test3 ")
iocLogInit()

cd /opt/EPICS/RUN/test3/startup
dbLoadTemplate "db/test3.substitutions"

iocInit

#caPutLog after iocInit
caPutLogInit "127.0.0.1:7004" 0

