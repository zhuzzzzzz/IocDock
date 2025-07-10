# Do not modified.

# Set EPICS ENV in running container
export EPICS_HOST_ARCH=$(${EPICS_BASE}/startup/EpicsHostArch)
export PATH=${PATH}:${EPICS_BASE}/bin/${EPICS_HOST_ARCH}
