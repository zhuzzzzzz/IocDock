#!/opt/EPICS/IOC/ST-IOC/bin/linux-x86_64/ST-IOC

cd /opt/EPICS/IOC/ST-IOC/iocBoot/iocST-IOC
< envPaths

cd "${TOP}"
dbLoadDatabase "dbd/ST-IOC.dbd"
ST_IOC_registerRecordDeviceDriver pdbbase

#autosave
epicsEnvSet REQ_DIR /opt/EPICS/RUN/test1/settings/autosave
epicsEnvSet SAVE_DIR /opt/EPICS/RUN/test1/log/autosave
set_requestfile_path("$(REQ_DIR)")
set_savefile_path("$(SAVE_DIR)")
set_pass0_restoreFile("$test1-automake-pass0.sav")
set_pass1_restoreFile("$test1-automake.sav")
save_restoreSet_DatedBackupFiles(1)
save_restoreSet_NumSeqFiles(3)
save_restoreSet_SeqPeriodInSeconds(600)
save_restoreSet_RetrySeconds(60)
save_restoreSet_CallbackTimeout(-1)


cd /opt/EPICS/RUN/test1/startup
dbLoadTemplate "db/test1.substitutions"
dbLoadRecords("db/status_ioc.db","IOC=test1")
dbLoadRecords("db/status_OS.db","HOST=test1:docker")

iocInit

#autosave after iocInit
makeAutosaveFileFromDbInfo("$(REQ_DIR)/$test1-automake-pass0.req", "autosaveFields_pass0")
makeAutosaveFileFromDbInfo("$(REQ_DIR)/$test1-automake.req", "autosaveFields")
create_monitor_set("$test1-automake-pass0.req",10)
create_monitor_set("$test1-automake.req",10)

