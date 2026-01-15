#!/usr/bin/python3

import os, shutil
from subprocess import Popen, TimeoutExpired, PIPE
import sys
import argparse

#
MODULES_TO_INSTALL = [
    "seq",
    "asyn",
    "StreamDevice",
    "caPutLog",
    "autosave",
    "iocStats",
    "modbus",
    "s7nodave",
    "BACnet",
]
IOC_NAME = "ST-IOC"
MODULES_DIR_NAME = "SUPPORT"

with_seq = False
seq_file_list = []

# Register supported modules.
# Format: {'path name': 'module name'}
MODULES_SUPPORTED = {
    "seq": "SNCSEQ",
    "asyn": "ASYN",
    "StreamDevice": "STREAM",
    "caPutLog": "caPutLog",
    "autosave": "AUTOSAVE",
    "iocStats": "IOCADMIN",
    "modbus": "MODBUS",
    "s7nodave": "S7NODAVE",
    "BACnet": "BACnet",
}
DEFAULT_MAKEFILE_TEMPLATE = [
    "#\n",
    "template_DBD += systemCommand.dbd\n",
    "\n",
    "#PVA\n",
    "ifdef EPICS_QSRV_MAJOR_VERSION\n",
    "\ttemplate_LIBS += qsrv\n",
    "\ttemplate_LIBS += $(EPICS_BASE_PVA_CORE_LIBS)\n",
    "\ttemplate_DBD += PVAServerRegister.dbd\n"
    "\ttemplate_DBD += qsrv.dbd\n"
    "endif\n"
    "\n",
]
MODULES_MAKEFILE_TEMPLATE = {
    "seq": [
        f"#SNCSEQ\n",
        f"template_LIBS += seq pv\n",
    ],
    "asyn": [
        f"#ASYN\n",
        f"template_DBD += drvVxi11.dbd\n",
        f"template_DBD += drvAsynSerialPort.dbd\n",
        f"template_DBD += drvAsynIPPort.dbd\n",
        f"template_LIBS += asyn\n",
        f"\n",
    ],
    "StreamDevice": [
        f"#STREAM\n",
        f"template_DBD += stream.dbd\n",
        f"template_DBD += asyn.dbd\n",
        f"template_LIBS += stream\n",
        f"\n",
    ],
    "caPutLog": [
        f"#caPutLog\n",
        f"template_LIBS += caPutLog\n",
        f"template_DBD += caPutLog.dbd\n",
        f"template_DBD += caPutJsonLog.dbd\n",
        f"\n",
    ],
    "autosave": [
        f"#AUTOSAVE\n",
        f"template_LIBS += autosave\n",
        f"template_DBD += asSupport.dbd\n",
        f"\n",
    ],
    "iocStats": [
        f"#IOCADMIN\n",
        f"template_LIBS += devIocStats\n",
        f"template_DBD += devIocStats.dbd\n",
        f"\n",
    ],
    "modbus": [
        f"#MODBUS\n",
        f"template_LIBS += modbus\n",
        f"template_DBD += modbusApp.dbd\n",
        f"template_DBD += modbusSupport.dbd\n",
        f"\n",
    ],
    "s7nodave": [
        f"#S7NODAVE\n",
        f"template_LIBS += s7nodave\n",
        f"template_DBD += s7nodave.dbd\n",
        f"\n",
    ],
    "BACnet": [
        f"#BACnet\n",
        f"template_LIBS += bacnetlib\n",
        f"template_DBD += bacnet.dbd\n",
        f"\n",
    ],
}


def try_makedirs(d):
    try:
        os.makedirs(d)
    except Exception as e:
        print(f'try_makedirs("{d}"): Failed, {e}.')
        return False
    else:
        print(f'try_makedirs("{d}"): Success.')
        return True


def file_remove(file_path, verbose=False):
    try:
        os.remove(file_path)
    except Exception as e:
        print(f'file_remove("{file_path}"): Failed, {e}.')
    else:
        if verbose:
            print(f'file_remove("{file_path}"): Success.')


def file_copy(src, dest, mode="r", verbose=False):
    """
    copy the file src to the file or directory dst.
    If dst specifies a directory, it must exist, the file will be copied into dst using the base filename from src.
    If dst specifies a directory not exist, dest will be considered as a file.
    If dst specifies a file that already exists, it will be replaced.

    :param src:
    :param dest:
    :param mode: a combination of "r", "w", "x" to set the file mode of current user
    :param verbose:
    :return: whether the execution was successful or not
    """
    if not os.path.isfile(src):
        print(f'file_copy: Failed, source "{src}" not found or is not file.')
        return False
    replace_flag = False
    # remove first if destination file exists(for some read-only files can not be replaced).
    if os.path.isfile(dest):
        if verbose:
            replace_flag = True
        file_remove(dest, verbose=False)
    elif os.path.isdir(dest):
        if os.path.isfile(os.path.join(dest, os.path.basename(src))):
            if verbose:
                replace_flag = True
            file_remove(os.path.join(dest, os.path.basename(src)), verbose=False)
    #
    try:
        res = shutil.copy(src, dest)
    except Exception as e:
        print(f"file_copy: Failed, {e}.")
        return False
    else:
        mode_number = 0o000
        if "r" in mode or "R" in mode:
            mode_number += 0o444
        if "w" in mode or "W" in mode:
            mode_number += 0o220
        if "x" in mode or "X" in mode:
            mode_number += 0o110
        if mode_number != 0o000:
            os.chmod(res, mode_number)
        else:
            os.chmod(res, 0o664)
        if verbose:
            print(
                f'file_copy: Success, {"replace" if replace_flag else "copy"} file '
                f'from "{src}" to "{res}" and set mode="{"DEFAULT" if mode_number == 0o000 else mode}".'
            )
        return True


def _escape_str(string: str):
    return string.replace("\n", "\\n")


# 读取文件，根据给定的字符串匹配位置，添加列表里的字符串至文件中第一个匹配的位置处
def add_lines(file_path, idx_str, str_list: list):
    with open(file_path, "r") as f:
        file = f.readlines()
    try:
        idx = file.index(idx_str)
    except ValueError:
        print(
            f'add_lines: 文件"{file_path}"中不存在与"{_escape_str(idx_str)}"匹配的文本行.'
        )
    else:
        first_half = file[0 : idx + 1]
        second_half = file[idx + 1 :]
        new_file = []
        new_file.extend(first_half)
        new_file.extend(str_list)
        new_file.extend(second_half)
        with open(file_path, "w") as f:
            f.writelines(new_file)


# Return module path from SUPPORT dir.
def get_module_path(support_dir):
    support_dir = os.path.normpath(support_dir)
    ls = os.listdir(support_dir)
    path_list = []
    module_list = []
    for ls_item in ls:
        if os.path.isdir(os.path.join(support_dir, ls_item)) and os.path.isdir(
            os.path.join(support_dir, ls_item, "lib")
        ):
            for path_name, module_name in MODULES_SUPPORTED.items():
                if path_name in ls_item and path_name in MODULES_TO_INSTALL:
                    path_list.append(
                        f"{module_name}={os.path.join(support_dir, ls_item)}\n"
                    )
                    module_list.append(module_name)
    return path_list


def parse_arguments():
    parser = argparse.ArgumentParser(description="Build IOC with specified modules")
    parser.add_argument(
        "--modules",
        nargs="+",
        help="List of modules to install, must be one of the modules defined in MODULES_SUPPORTED",
    )
    parser.add_argument(
        "--with-seq",
        action="store_true",
        help="Enable seq module installation (default: False)",
        default=False,
    )

    args = parser.parse_args()

    if args.modules:
        # 验证传入的模块是否都在MODULES_SUPPORTED的键中
        invalid_modules = [m for m in args.modules if m not in MODULES_SUPPORTED.keys()]
        if invalid_modules:
            print(f"Error: Invalid modules provided: {', '.join(invalid_modules)}")
            sys.exit(1)

        # 更新MODULES_TO_INSTALL
        global MODULES_TO_INSTALL
        MODULES_TO_INSTALL = args.modules

    if args.with_seq:
        global with_seq
        with_seq = True
        if "seq" not in MODULES_TO_INSTALL:
            MODULES_TO_INSTALL.append("seq")


def preparation_for_seq():
    print("Preparing for installing seq...")
    seq_dir = os.path.join(os.path.dirname(os.getcwd()), "src", "seq")
    if not os.path.exists(seq_dir):
        print(f'warning: directory "{seq_dir}" is not exist.')
        return False

    # 获取所有.stt文件
    stt_files = [f for f in os.listdir(seq_dir) if f.endswith(".stt")]
    if not stt_files:
        print(f'warning: no ".stt" files found in "{seq_dir}".')
        return False
    print(f"Found \".stt\" files: {', '.join(stt_files)}")

    #
    for item in stt_files:
        MODULES_MAKEFILE_TEMPLATE["seq"].append(f"template_SRCS += {item}\n")
    else:
        MODULES_MAKEFILE_TEMPLATE["seq"].append("template_DBD += sncPrograms.dbd\n")
        MODULES_MAKEFILE_TEMPLATE["seq"].append("\n")
    #
    with open(os.path.join(os.getcwd(), "sncPrograms.dbd"), "w") as f:
        for item in stt_files:
            program_name = item[:-4]
            f.write(f"registrar({program_name}Registrar)\n")

    global seq_file_list
    seq_file_list = stt_files

    return True


def main():
    #
    if with_seq:
        preparation_for_seq()
    #
    tool_path = os.getcwd()
    top_dir = os.path.normpath(os.path.join(os.getcwd(), ".."))
    ioc_top_dir = os.path.join(top_dir, IOC_NAME)
    seq_src_dir = os.path.normpath(os.path.join(top_dir, "src", "seq"))

    # Create IOC directory
    print(f"Creating IOC project...")
    print(f"MODULES_TO_INSTALL: {', '.join(MODULES_TO_INSTALL)}")
    create_flag = False
    if os.path.isdir(ioc_top_dir):
        print(f"IOC project directory exists, deleting it...")
        if os.system(f"rm -rf {ioc_top_dir}"):
            print(f"Failed to delete IOC project directory.")
            sys.exit(1)
        else:
            print(f"Successfully deleted IOC project directory.")
    try_makedirs(ioc_top_dir)
    print(f'Move to "{ioc_top_dir}".')
    os.chdir(ioc_top_dir)
    # makeBaseApp.pl -t ioc ST_IOC
    print(f"Execute makeBaseApp.pl -t ioc {IOC_NAME}.")
    os.system(f"makeBaseApp.pl -t ioc {IOC_NAME}")
    # makeBaseApp.pl -i -t ioc ST_IOC
    print(f"Execute makeBaseApp.pl -i -t ioc {IOC_NAME}.")
    proc = Popen(
        args=f"makeBaseApp.pl -i -t ioc {IOC_NAME}",
        shell=True,
        encoding="utf-8",
        stdin=PIPE,
        stdout=PIPE,
        stderr=PIPE,
    )
    try:
        outs, errs = proc.communicate(input=f"{IOC_NAME}\n", timeout=15)
        print()
        print(outs)
        print(f"{IOC_NAME}")
        print()
        if errs:
            print(f"problem encountered when creating IOC directory: {errs}.")
    except TimeoutExpired:
        proc.kill()
        outs, errs = proc.communicate()
        print(outs)
        if errs:
            print(f"problem encountered when creating IOC directory: {errs}.")
    else:
        print(f"Create IOC directory at {ioc_top_dir}.")
        create_flag = True

    if not create_flag:
        print(f"error: failed to create IOC directory.")
        exit(1)

    # Allow execute permission to st.cmd.
    file_path = os.path.join(ioc_top_dir, "iocBoot", f"ioc{IOC_NAME}", "st.cmd")
    os.system(f"chmod u+x {file_path}")

    # Generate configure/RELEASE.
    support_dir_path = os.path.normpath(os.path.join(top_dir, "..", MODULES_DIR_NAME))
    lines_to_add = get_module_path(support_dir_path)
    if lines_to_add:
        file_path = os.path.join(top_dir, "RELEASE.local")
        with open(file_path, "w") as f:
            f.writelines(lines_to_add)
            print(f'Create RELEASE.local at "{file_path}".')
    else:
        print(f"failed to create RELEASE.local.")
        exit(1)

    # Copy .dbd files
    print(f'Copy file "systemCommand.dbd".')
    file_copy(
        os.path.join(tool_path, "systemCommand.dbd"),
        os.path.join(ioc_top_dir, f"{IOC_NAME}App", "src", "systemCommand.dbd"),
        mode="rw",
        verbose=True,
    )

    # Handle Makefile
    print(f"Handle IOC Makefile.")
    lines_to_add = [
        "\n",
    ]
    lines_to_add.extend(DEFAULT_MAKEFILE_TEMPLATE)
    # if sequencer to be installed, add src files.
    if with_seq:
        dest_dir = os.path.join(ioc_top_dir, f"{IOC_NAME}App", "src")
        file_copy(
            os.path.join(tool_path, "sncPrograms.dbd"),
            os.path.join(dest_dir, "sncPrograms.dbd"),
            mode="r",
            verbose=True,
        )
        for st_file in seq_file_list:
            file_copy(
                os.path.join(seq_src_dir, st_file),
                os.path.join(dest_dir, st_file),
                mode="r",
                verbose=True,
            )
    for item in MODULES_TO_INSTALL:
        lines_to_add.extend(MODULES_MAKEFILE_TEMPLATE[item])
    for i in range(0, len(lines_to_add)):
        lines_to_add[i] = lines_to_add[i].replace("template", IOC_NAME)
    file_path = os.path.join(ioc_top_dir, f"{IOC_NAME}App", "src", "Makefile")
    add_lines(file_path, f"#{IOC_NAME}_LIBS += xxx\n", lines_to_add)

    # If set asyn, handle DB_install
    if "asyn" in MODULES_TO_INSTALL:
        file_path = os.path.join(ioc_top_dir, f"{IOC_NAME}App", "Db", "Makefile")
        add_lines(
            file_path, f"#DB += xxx.db\n", ["DB_INSTALLS += $(ASYN)/db/asynRecord.db\n"]
        )
        print(f"Handled IOC Makefile for asyn.")

    print(f'Finish handling "Makefile" at {file_path}.')

    # execute make
    os.chdir(ioc_top_dir)
    print(f"Move to {ioc_top_dir}\n then execute make...")
    if os.system("make"):
        print(f"error: failed to execute make.")
        exit(1)
    else:
        print(f"Deleting immediate files...")
        file_remove(os.path.join(tool_path, "sncPrograms.dbd"), verbose=False)
        print(f"Successfully Build IOC Project.")
        print(f"Installed modules: {', '.join(MODULES_TO_INSTALL)}")


if __name__ == "__main__":
    parse_arguments()
    main()
