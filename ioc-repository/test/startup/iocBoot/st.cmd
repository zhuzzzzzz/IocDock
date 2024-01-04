#!/opt/EPICS/IOC/ST-IOC/bin/linux-x86_64/ST-IOC

cd /opt/EPICS/IOC/ST-IOC/iocBoot/iocST-IOC
< envPaths

cd "${TOP}"
dbLoadDatabase "dbd/ST-IOC.dbd"
ST_IOC_registerRecordDeviceDriver pdbbase

#autosave
epicsEnvSet REQ_DIR /opt/EPICS/RUN/test/settings/autosave
epicsEnvSet SAVE_DIR /opt/EPICS/RUN/test/log/autosave
set_requestfile_path("$(REQ_DIR)")
set_savefile_path("$(SAVE_DIR)")
set_pass0_restoreFile("$test-automake-pass0.sav")
set_pass1_restoreFile("$test-automake.sav")
save_restoreSet_DatedBackupFiles(1)
save_restoreSet_NumSeqFiles(3)
save_restoreSet_SeqPeriodInSeconds(600)
save_restoreSet_RetrySeconds(60)
save_restoreSet_CallbackTimeout(-1)

#caPutLog
asSetFilename("/opt/EPICS/RUN/test/settings/test.acf")
epicsEnvSet("EPICS_IOC_LOG_INET","127.0.0.1")
iocLogPrefix("test ")
iocLogInit()

cd /opt/EPICS/RUN/test/startup
dbLoadTemplate "db/test.substitutions"
dbLoadRecords("db/status_ioc.db","IOC=test")

iocInit

#autosave after iocInit
makeAutosaveFileFromDbInfo("$(REQ_DIR)/$test-automake-pass0.req", "autosaveFields_pass0")
makeAutosaveFileFromDbInfo("$(REQ_DIR)/$test-automake.req", "autosaveFields")
create_monitor_set("$test-automake-pass0.req",10)
create_monitor_set("$test-automake.req",10)

#caPutLog after iocInit
caPutLogInit "127.0.0.1:7004" 0

