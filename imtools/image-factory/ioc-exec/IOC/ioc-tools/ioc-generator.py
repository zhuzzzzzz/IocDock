#!/usr/bin/python3

import os, shutil
from subprocess import Popen, TimeoutExpired, PIPE

###
# Codes can be modified.

# Set IOC name
IOC_NAME = 'ST-IOC'

# Set which module to be installed with IOC
# 'path name': 'module name'
MODULES_TO_INSTALL = {
    'seq': 'SNCSEQ',
    'asyn': 'ASYN',
    'StreamDevice': 'STREAM',
    'caPutLog': 'caPutLog',
    'autosave': 'AUTOSAVE',
    'iocStats': 'IOCADMIN',
    'modbus': 'MODBUS',
    's7nodave': 'S7NODAVE',
}

# If seq to be installed, make configurations here
# You should set .st file list and the definitions of IOC Makefile, You can refer to the settings below to set seq.
seq_file_list = ['sncExample.dbd', 'sncExample.stt']
Makefile_template_for_seq = [
    f'sncExample_SNCFLAGS += +r\n',
    f'template_DBD += sncExample.dbd\n',
    f'template_SRCS += sncExample.stt\n',
    f'template_LIBS += seq pv\n',
]

###
# Codes should not be modified.
MODULES_DIR_NAME = 'SUPPORT'
Makefile_template_for_all = [
    '#\n',
    'template_DBD += systemCommand.dbd\n',
    '\n',
    '#PVA\n',
    'ifdef EPICS_QSRV_MAJOR_VERSION\n',
    '\ttemplate_LIBS += qsrv\n'
    '\ttemplate_LIBS += $(EPICS_BASE_PVA_CORE_LIBS)\n',
    '\ttemplate_DBD += PVAServerRegister.dbd\n'
    '\ttemplate_DBD += qsrv.dbd\n'
    'endif\n'
    '\n',
]
Makefile_template_for_modules = {
    'seq': [
        f'#SNCSEQ\n',
        # f'template_LIBS += seq pv\n',
    ],
    'asyn': [
        f'#ASYN\n',
        f'template_DBD += drvVxi11.dbd\n',
        f'template_DBD += drvAsynSerialPort.dbd\n',
        f'template_DBD += drvAsynIPPort.dbd\n',
        f'template_LIBS += asyn\n',
        f'\n',
    ],
    'StreamDevice': [
        f'#STREAM\n',
        f'template_DBD += stream.dbd\n',
        f'template_DBD += asyn.dbd\n',
        f'template_LIBS += stream\n',
        f'\n',
    ],
    'caPutLog': [
        f'#caPutLog\n',
        f'template_LIBS += caPutLog\n',
        f'template_DBD += caPutLog.dbd\n',
        f'template_DBD += caPutJsonLog.dbd\n',
        f'\n',
    ],
    'autosave': [
        f'#AUTOSAVE\n',
        f'template_LIBS += autosave\n',
        f'template_DBD += asSupport.dbd\n',
        f'\n',
    ],
    'iocStats': [
        f'#IOCADMIN\n',
        f'template_LIBS += devIocStats\n',
        f'template_DBD += devIocStats.dbd\n',
        f'\n',
    ],
    'modbus': [
        f'#IOCADMIN\n',
        f'template_LIBS += modbus\n',
        f'template_DBD += modbusApp.dbd\n',
        f'template_DBD += modbusSupport.dbd\n',
        f'\n',
    ],
    's7nodave': [
        f'#S7NODAVE\n',
        f'template_LIBS += s7nodave\n',
        f'template_DBD += s7nodave.dbd\n',
        f'\n',
    ],
}


def try_makedirs(d):
    try:
        os.makedirs(d)
    except FileExistsError:
        print(f'try_makedirs("{d}"): FileExistsError Exception.')
        return False
    else:
        print(f'try_makedirs("{d}"): Success.')
        return True


def file_remove(file_path, verbose=False):
    try:
        os.remove(file_path)
    except OSError as e:
        print(f'file_remove: "{file_path}" removed failed, {e}.')
    else:
        if verbose:
            print(f'file_remove: "{file_path}" removed.')


def file_copy(src, dest, mode='r', verbose=False):
    if not os.path.exists(src):
        print(f'file_copy: failed, "{src}" source file not found.')
        return False
    # if destination file exists, remove it.
    if os.path.exists(dest):
        if verbose:
            print(f'file_copy: destination "{dest}" exists, first remove it.')
        file_remove(dest, verbose)
    # if destination dir no exists, create it.
    dest_dir = os.path.dirname(dest)
    if not os.path.isdir(dest_dir):
        if verbose:
            print(f'file_copy: destination directory "{dest_dir}" not exists, first create it.')
        try_makedirs(dest_dir)

    try:
        shutil.copy(src, dest)
    except PermissionError as e:
        print(f'file_copy: failed, {e}.')
        return False
    except Exception as e:
        print(f'file_copy: failed, {e}.')
        return False
    else:
        if verbose:
            print(f'file_copy: success, copy file from "{src}" to "{dest}.')
        mode_number = 0o000
        if 'r' in mode or 'R' in mode:
            mode_number += 0o444
            if verbose:
                print(f'file_copy: set "{dest}" as readable.')
        if 'w' in mode or 'W' in mode:
            mode_number += 0o220
            if verbose:
                print(f'file_copy: set "{dest}" as writable.')
        if 'x' in mode or 'X' in mode:
            mode_number += 0o110
            if verbose:
                print(f'file_copy: set "{dest}" as executable.')
        if mode_number != 0o000:
            os.chmod(dest, mode_number)
        return True


def _escape_str(string: str):
    return string.replace('\n', '\\n')


# 读取文件，根据给定的字符串匹配位置，添加列表里的字符串至文件中匹配的位置处
def add_lines(file_path, idx_str, str_list: list):
    with open(file_path, 'r') as f:
        file = f.readlines()
    try:
        idx = file.index(idx_str)
    except ValueError:
        print(f'add_lines: 文件"{file_path}"中不存在与"{_escape_str(idx_str)}"匹配的文本行.')
    else:
        first_half = file[0:idx + 1]
        second_half = file[idx + 1:]
        new_file = []
        new_file.extend(first_half)
        new_file.extend(str_list)
        new_file.extend(second_half)
        with open(file_path, 'w') as f:
            f.writelines(new_file)


# return module path from SUPPORT dir.
def get_module_path(d):
    d = os.path.normpath(d)
    ls = os.listdir(d)
    path_list = []
    module_list = []
    for ls_item in ls:
        if os.path.isdir(os.path.join(d, ls_item)) and os.path.isdir(os.path.join(d, ls_item, 'lib')):
            for path_name, module_name in MODULES_TO_INSTALL.items():
                if path_name in ls_item:
                    path_list.append(f'{module_name}={os.path.join(d, ls_item)}\n')
                    module_list.append(module_name)
    for item in MODULES_TO_INSTALL.values():
        if item not in module_list:
            print(f'module "{item}" not found in "{d}" directory.')
            return None
    return path_list


def main():
    # For IOC with sequencer, checking files and make settings in Makefile.
    with_seq = False
    if 'seq' in MODULES_TO_INSTALL.keys():
        with_seq = True
        if seq_file_list:
            for item in seq_file_list:
                if item not in os.listdir():
                    print(f'file "{item}" set for sequencer but not found in "{os.getcwd()}".')
                    exit(1)
            else:
                Makefile_template_for_modules['seq'].extend(Makefile_template_for_seq)
                Makefile_template_for_modules['seq'].append(f'\n')
        else:
            print(f'sequencer is set to be installed but related files are not set.')
            exit(1)

    tool_path = os.getcwd()
    top_dir = os.path.normpath(os.path.join(os.getcwd(), '..'))

    # create IOC directory
    create_flag = False
    ioc_top_dir = os.path.join(top_dir, IOC_NAME)
    try_makedirs(ioc_top_dir)
    os.chdir(ioc_top_dir)
    print(f'move to "{ioc_top_dir}".')
    print(f'execute makeBaseApp.pl -t ioc {IOC_NAME}.')
    os.system(f'makeBaseApp.pl -t ioc {IOC_NAME}')
    print(f'execute makeBaseApp.pl -i -t ioc {IOC_NAME}.')
    #
    proc = Popen(args=f'makeBaseApp.pl -i -t ioc {IOC_NAME}', shell=True, encoding='utf-8', stdin=PIPE, stdout=PIPE,
                 stderr=PIPE)
    try:
        outs, errs = proc.communicate(input=f'{IOC_NAME}\n', timeout=15)
        print(outs)
        print(f'{IOC_NAME}')
        if errs:
            print(f'problem encountered when creating IOC directory: {errs}.')
    except TimeoutExpired:
        proc.kill()
        outs, errs = proc.communicate()
        print(outs)
        if errs:
            print(f'problem encountered when creating IOC directory: {errs}.')
    else:
        print(f'create IOC directory at {ioc_top_dir}.')
        create_flag = True

    if not create_flag:
        print(f'failed to create IOC directory.')
    else:
        # execute permission to st.cmd
        file_path = os.path.join(ioc_top_dir, 'iocBoot', f'ioc{IOC_NAME}', 'st.cmd')
        os.system(f'chmod u+x {file_path}')

        # handle configure/RELEASE
        support_dir_path = os.path.normpath(os.path.join(top_dir, '..', MODULES_DIR_NAME))
        lines_to_add = get_module_path(support_dir_path)
        if lines_to_add:
            file_path = os.path.join(top_dir, 'RELEASE.local')
            with open(file_path, 'w') as f:
                f.writelines(lines_to_add)
                print(f'create RELEASE.local at "{file_path}".')
        else:
            print(f'failed to create RELEASE.local.')
            exit(1)

        # copy .dbd files
        file_copy(os.path.join(tool_path, 'systemCommand.dbd'),
                  os.path.join(ioc_top_dir, f'{IOC_NAME}App', 'src', 'systemCommand.dbd'), mode='rw', verbose=True)

        # handle Makefile
        lines_to_add = ['\n', ]
        lines_to_add.extend(Makefile_template_for_all)
        # if sequencer defined, add src files.
        if with_seq:
            dest_dir = os.path.join(ioc_top_dir, f'{IOC_NAME}App', 'src')
            for st_file in seq_file_list:
                file_copy(os.path.join(tool_path, st_file), os.path.join(dest_dir, st_file), mode='r', verbose=True)
        for key, value in MODULES_TO_INSTALL.items():
            lines_to_add.extend(Makefile_template_for_modules[key])
        for i in range(0, len(lines_to_add)):
            lines_to_add[i] = lines_to_add[i].replace('template', IOC_NAME)
        file_path = os.path.join(ioc_top_dir, f'{IOC_NAME}App', 'src', 'Makefile')
        add_lines(file_path, f'#{IOC_NAME}_LIBS += xxx\n', lines_to_add)
        print(f'handled Makefile at {file_path}.')

        # if asyn set, handle DB_install
        if 'asyn' in MODULES_TO_INSTALL.keys():
            file_path = os.path.join(ioc_top_dir, f'{IOC_NAME}App', 'Db', 'Makefile')
            add_lines(file_path, f'#DB += xxx.db\n', ['DB_INSTALLS += $(ASYN)/db/asynRecord.db\n'])
            print(f'handled Makefile at {file_path} for asyn.')

        # execute make
        os.chdir(ioc_top_dir)
        print(f'move to {ioc_top_dir}\nmake...')
        os.system('make')


if __name__ == "__main__":
    main()
