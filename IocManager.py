#!/usr/bin/python3
import argparse
import configparser
import yaml
import os
import datetime
import tarfile
from collections.abc import Iterable
from tabulate import tabulate

from imtools.IMFuncsAndConst import (try_makedirs, dir_copy, file_copy, condition_parse, dir_remove,
                                     relative_and_absolute_path_to_abs, check_snapshot_file, add_snapshot_file,
                                     MOUNT_DIR, REPOSITORY_DIR, CONFIG_FILE_NAME, CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR,
                                     BACKUP_DIR, )
from imtools.IocClass import IOC


# accepts iterable for input
def create_ioc(name, args, config=None, verbose=False):
    if isinstance(name, str):
        # May add a name string filter here?
        #
        dir_path = os.path.join(os.getcwd(), REPOSITORY_DIR, name)
        if os.path.exists(os.path.join(dir_path, CONFIG_FILE_NAME)):
            print(f'create_ioc: Failed. IOC "{name}" already exists.')
        else:
            # Create an IOC and do initialization by given configparser.ConfigParser() object.
            try_makedirs(dir_path, verbose)
            ioc_temp = IOC(dir_path, verbose=verbose)
            if args.add_asyn:
                ioc_temp.add_asyn_template(args.port_type)
                if verbose:
                    print(f'create_ioc: add asyn template for IOC "{name}".')
            if args.add_stream:
                ioc_temp.add_stream_template(args.port_type)
                if verbose:
                    print(f'create_ioc: add stream template for IOC "{name}".')
            if args.add_raw:
                ioc_temp.add_raw_cmd_template()
                if verbose:
                    print(f'create_ioc: add raw command template for IOC "{name}".')
            if config:
                for section in config.sections():
                    for option in config.options(section):
                        if section == 'IOC' and option == 'name':  # Name should not be directly copied.
                            continue
                        if section == 'IOC' and option == 'status':  # status should not be directly copied.
                            continue
                        if section == 'IOC' and option == 'snapshot':  # snapshot should not be directly copied.
                            continue
                        value = config.get(section, option)
                        ioc_temp.set_config(option, value, section)
            print(f'create_ioc: Success. IOC "{name}" created.')
            ioc_temp.check_consistency()
            if args.print_ioc:
                ioc_temp.show_config()
    elif isinstance(name, Iterable):
        for n in name:
            create_ioc(n, args, config=config, verbose=verbose)
    else:
        print(f'create_ioc: Failed. Invalid input args: "{name}".')


# not accept iterable for input
def set_ioc(name, args, config=None, verbose=False):
    if isinstance(name, str):
        dir_path = os.path.join(os.getcwd(), REPOSITORY_DIR, name)
        if os.path.exists(os.path.join(dir_path, CONFIG_FILE_NAME)):
            # Initialize an existing IOC, edit ioc.ini by given configparser.ConfigParser() object.
            ioc_temp = IOC(dir_path, verbose)
            modify_flag = False
            if args.add_asyn:
                ioc_temp.add_asyn_template(args.port_type)
                modify_flag = True
                if verbose:
                    print(f'set_ioc: add asyn template for IOC "{name}".')
            if args.add_stream:
                ioc_temp.add_stream_template(args.port_type)
                modify_flag = True
                if verbose:
                    print(f'set_ioc: add stream template for IOC "{name}".')
            if args.add_raw:
                ioc_temp.add_raw_cmd_template()
                modify_flag = True
                if verbose:
                    print(f'set_ioc: add raw command template for IOC "{name}".')
            if any(config.options(section) for section in config.sections()):
                for section in config.sections():
                    for option in config.options(section):
                        if section == 'IOC' and option == 'name':
                            continue
                        if section == 'IOC' and option == 'status':
                            continue
                        if section == 'IOC' and option == 'snapshot':
                            continue
                        value = config.get(section, option)
                        ioc_temp.set_config(option, value, section)
                modify_flag = True
            ioc_temp.check_consistency()
            if modify_flag:
                if verbose:
                    print(f'set_ioc: Success. IOC "{name}" modified by given settings.')
                if args.print_ioc:
                    ioc_temp.show_config()
            else:
                if verbose:
                    print(f'set_ioc: No setting was given for IOC "{name}".')
        else:
            print(f'set_ioc: Failed. IOC "{name}" not exist.')
    else:
        print(f'set_ioc: Failed. Invalid input args "{name}".')


# Remove only generated files or remove all files.
# do not accept iterable for input
def remove_ioc(name, all_remove=False, force_removal=False, verbose=False):
    dir_path = os.path.join(os.getcwd(), REPOSITORY_DIR, name)
    if os.path.exists(os.path.join(dir_path, CONFIG_FILE_NAME)):
        if not force_removal:
            if all_remove:
                print(f'remove_ioc: IOC "{name}" will be removed completely.', end='')
            else:
                print(f'remove_ioc: Remove IOC "{name}" partially. only the generated files will be removed,'
                      f' "src/" directory and settings file will be preserved.', end='')
            ans = input(f'Continue?[y|n]:')
            if ans.lower() == 'y' or ans.lower() == 'yes':
                force_removal = True
            elif ans.lower() == 'n' or ans.lower() == 'no':
                print(f'remove_ioc: Remove canceled.')
            else:
                print(f'remove_ioc: Failed. Invalid input, remove canceled.')
        if force_removal:
            ioc_temp = IOC(dir_path, verbose)
            ioc_temp.remove(all_remove)
            if all_remove:
                print(f'remove_ioc: Success. IOC "{name}" removed completely.')
            else:
                print(f'remove_ioc: Success. IOC "{name}" removed, directory "src/" and file "ioc.ini" are preserved.')
    else:
        print(f'remove_ioc: Failed. IOC "{name}" not found.')


# Get IOC projects in given name list for given path. return object list of all IOC projects, if name list not given.
def get_all_ioc(dir_path=None, from_list=None):
    ioc_list = []
    if not dir_path:
        dir_path = os.path.join(os.getcwd(), REPOSITORY_DIR)
    items = os.listdir(dir_path)
    if from_list:
        temp_items = []
        for i in items:
            if i in from_list:
                temp_items.append(i)
        else:
            items = temp_items
    items.sort()  # sort according to name string.
    for ioc_name in items:
        subdir_path = os.path.join(dir_path, ioc_name)
        if os.path.isdir(subdir_path) and CONFIG_FILE_NAME in os.listdir(subdir_path):
            ioc_list.append(IOC(subdir_path))
    return ioc_list


# Show IOC projects that meeting the specified conditions and section, AND logic is implied to each condition.
def get_filtered_ioc(condition: Iterable, section='IOC', from_list=None, raw_info=False, show_info=False,
                     verbose=False):
    section = section.upper()  # to support case-insensitive filter for section.

    ioc_list = get_all_ioc(from_list=from_list)
    if from_list is not None:
        print(f'List IOC projects from "{from_list}":')

    index_to_remove = []
    if not condition:
        # Filter IOC projects by section when no condition specified.
        # Default will return all IOC projects, because all IOC projects have section "IOC".
        for i in range(0, len(ioc_list)):
            if not ioc_list[i].conf.has_section(section=section):
                index_to_remove.append(i)
        if verbose:
            print(f'No condition specified, list IOC projects that has section "{section}":')
    elif isinstance(condition, str):
        key, value = condition_parse(condition)
        if key:
            if key.lower() != 'name':
                for i in range(0, len(ioc_list)):
                    if not ioc_list[i].check_config(key, value, section):
                        index_to_remove.append(i)
                if verbose:
                    print(f'Results for section "{section}", condition "{condition}":')
            else:
                for i in range(0, len(ioc_list)):
                    if value not in ioc_list[i].name:
                        index_to_remove.append(i)
                if verbose:
                    print(f'Results for name matching:')
        else:
            # Do not return any result when wrong condition parsed.
            index_to_remove = [i for i in range(0, len(ioc_list))]
            if verbose:
                print(f'No result. Invalid condition specified: "{condition}".')
    elif isinstance(condition, Iterable):
        valid_flag = False  # flag to check whether any valid condition has been given.
        valid_condition = []
        for c in condition:
            key, value = condition_parse(c)
            # only valid condition was parsed to filter IOC.
            if key:
                valid_flag = True
                valid_condition.append(c)
                if key.lower() != 'name':
                    for i in range(0, len(ioc_list)):
                        if not ioc_list[i].check_config(key, value, section):
                            index_to_remove.append(i)
                else:
                    for i in range(0, len(ioc_list)):
                        if value not in ioc_list[i].name:
                            index_to_remove.append(i)
            else:
                if verbose:
                    print(f'Skipped invalid condition "{c}".')
        if valid_flag:
            if verbose:
                print(f'Results for section "{section}", condition "{valid_condition}":')
        else:
            # Do not return any result, if there is no valid condition given.
            index_to_remove = [i for i in range(0, len(ioc_list))]
            if verbose:
                print(f'No result. No valid condition specified: "{condition}".')
    else:
        index_to_remove = [i for i in range(0, len(ioc_list))]  # remove all
        if verbose:
            print(f'No result. Invalid condition: "{condition}".')

    # get index to print.
    index_to_preserve = []
    for i in range(0, len(ioc_list)):
        if i in index_to_remove:
            continue
        else:
            index_to_preserve.append(i)
    # print results.
    raw_print = [["Name", "Host", "Status", "Snapshot"], ]
    for i in index_to_preserve:
        if show_info:
            ioc_list[i].show_config()
        elif raw_info:
            raw_print.append([ioc_list[i].name, ioc_list[i].get_config("host"), ioc_list[i].get_config("status"),
                              ioc_list[i].get_config("snapshot")])
            # print(f'{ioc_list[i].name}\t\t\t{ioc_list[i].get_config("host")}\t\t\t{ioc_list[i].get_config("status")}')
        else:
            print(ioc_list[i].name)
    else:
        if raw_info:
            print(tabulate(raw_print, headers="firstrow", tablefmt='plain'))

    for i in index_to_preserve:
        ioc_list[i].check_consistency()


def execute_ioc(args):
    # operation for all IOC projects.
    if args.gen_compose_file:
        gen_compose_files(base_image=args.base_image, mount_dir=args.mount_path, verbose=args.verbose)
    elif args.gen_backup_file:
        repository_backup(backup_mode=args.backup_mode, backup_dir=args.backup_path, verbose=args.verbose)
    elif args.restore_backup_file:
        restore_backup(backup_path=args.backup_file, force_overwrite=args.force_overwrite, verbose=args.verbose)
    elif args.run_check:
        for ioc_temp in get_all_ioc():
            ioc_temp.check_consistency(run_check=True)
    else:
        # operation for specified IOC projects.
        if not args.name:
            print(f'execute_ioc: No IOC project specified.')
        else:
            for name in args.name:
                dir_path = os.path.join(os.getcwd(), REPOSITORY_DIR, name)
                if os.path.exists(os.path.join(dir_path, CONFIG_FILE_NAME)):
                    if args.verbose:
                        print('')
                        print(f'execute_ioc: dealing with IOC "{name}".')
                    ioc_temp = IOC(dir_path, args.verbose)
                    if args.add_src_file:
                        ioc_temp.get_src_file(src_dir=args.src_path)
                    elif args.gen_startup_file:
                        ioc_temp.generate_startup_files(force_executing=args.force_silent,
                                                        force_default=args.force_default)
                    elif args.export_for_mount:
                        export_for_mount(name, mount_dir=args.mount_path, force_overwrite=args.force_overwrite,
                                         verbose=args.verbose)
                    else:
                        print(f'execute_ioc: No "exec" operation specified.')
                        break  # break to avoid repeat print of "no exec" operation.
                else:
                    print(f'execute_ioc: Failed. IOC "{name}" not found.')
            else:
                if args.verbose:
                    print('')


# Generate directory structure of an IOC project for running inside the container.
# mount_dir: a top path for MOUNT_DIR.
# force_overwrite: "True" overwrite all files of existing IOC project in mount dir.
# force_overwrite: "False" only overwrite files that are not generated during running.
def export_for_mount(name, mount_dir=None, force_overwrite=False, verbose=False):
    dir_path = os.path.join(os.getcwd(), REPOSITORY_DIR, name)
    ioc_temp = IOC(dir_path, verbose)

    if not (ioc_temp.check_config('status', 'generated') or ioc_temp.check_config('status', 'exported')):
        print(f'export_for_mount: Failed. Export checks failed for IOC {name}, startup files should be generated.')
        return
    if not check_snapshot_file(name, verbose):
        print(f'export_for_mount: Failed. Export checks failed for IOC {name}, '
              f'Settings has been changed, startup files should be re-generated.')
        ioc_temp.set_config('snapshot', 'changed')
        return

    container_name = ioc_temp.get_config('container')
    host_name = ioc_temp.get_config('host')
    if not container_name:
        container_name = ioc_temp.name
        if verbose:
            print(f'export_for_mount: Option "container" not defined in IOC "{ioc_temp.name}", '
                  f'automatically use IOC name as container name.')
    if not host_name:
        host_name = 'localhost'
        if verbose:
            print(f'export_for_mount: Option "host" not defined in IOC "{ioc_temp.name}", '
                  f'automatically use "localhost" as host name.')

    mount_path = relative_and_absolute_path_to_abs(mount_dir, '..')
    if not os.path.isdir(mount_path):
        print(f'export_for_mount: Failed. Path for mounting "{mount_path}" not exists.')
        return

    top_path = os.path.join(mount_path, MOUNT_DIR, host_name, container_name)
    if not os.path.isdir(top_path):
        file_to_copy = ('ioc.ini',)
        dir_to_copy = ('settings', 'log', 'startup',)
        for item_file in file_to_copy:
            file_copy(os.path.join(ioc_temp.dir_path, item_file), os.path.join(top_path, item_file), verbose=verbose)
            # set readonly permission.
            os.chmod(os.path.join(top_path, item_file), mode=0o444)
        for item_dir in dir_to_copy:
            if not dir_copy(os.path.join(ioc_temp.dir_path, item_dir), os.path.join(top_path, item_dir), verbose):
                print(f'export_for_mount: Failed. You may run this command again with "-v" option to see '
                      f'what happened for IOC "{name}" in details.')
                return
        else:
            print(f'export_for_mount: Success. IOC "{name}" created in {top_path}.')
    elif os.path.isdir(top_path) and force_overwrite:
        file_to_copy = ('ioc.ini',)
        dir_to_copy = ('settings', 'log', 'startup',)
        for item_file in file_to_copy:
            file_copy(os.path.join(ioc_temp.dir_path, item_file), os.path.join(top_path, item_file), verbose=verbose)
            # set readonly permission.
            os.chmod(os.path.join(top_path, item_file), mode=0o444)
        for item_dir in dir_to_copy:
            if not dir_copy(os.path.join(ioc_temp.dir_path, item_dir), os.path.join(top_path, item_dir), verbose):
                print(f'export_for_mount: Failed. You may run this command again with "-v" option to see '
                      f'what happened for IOC "{name}" in details.')
                return
        else:
            print(f'export_for_mount: Success. IOC "{name}" overwrite in {top_path}.')
    elif os.path.isdir(top_path) and not force_overwrite:
        file_to_copy = ('ioc.ini',)
        dir_to_copy = ('startup',)
        for item_file in file_to_copy:
            file_copy(os.path.join(ioc_temp.dir_path, item_file), os.path.join(top_path, item_file), verbose=verbose)
            # set readonly permission.
            os.chmod(os.path.join(top_path, item_file), mode=0o444)
        for item_dir in dir_to_copy:
            if not dir_copy(os.path.join(ioc_temp.dir_path, item_dir), os.path.join(top_path, item_dir), verbose):
                print(f'export_for_mount: Failed. You may run this command again with "-v" option to see '
                      f'what happened for IOC "{name}" in details.')
                return
        else:
            print(f'export_for_mount: Success. IOC "{name}" updated in {top_path}.')
    ioc_temp.set_config('status', 'exported')
    # add ioc.ini snapshot file
    add_snapshot_file(name, verbose)


# Generate Docker Compose file for all hosts and IOC projects in given path.
# base_image: image with epics base for iocLogServer.
# mount_dir: top dir for MOUNT_DIR.
def gen_compose_files(base_image, mount_dir, verbose):
    mount_path = relative_and_absolute_path_to_abs(mount_dir, '.')
    top_path = os.path.join(mount_path, MOUNT_DIR)
    if not os.path.isdir(top_path):
        print(f'gen_compose_files: Failed. Working directory {top_path} is not exist!')
        return
    else:
        if verbose:
            print(f'gen_compose_files: Working at {top_path}.')

    for host_dir in os.listdir(top_path):
        host_path = os.path.join(top_path, host_dir)
        if not os.path.isdir(host_path):
            continue
        # get valid IOC projects
        ioc_list = []
        for ioc_dir in os.listdir(host_path):
            ioc_path = os.path.join(host_path, ioc_dir, 'ioc.ini')
            if not os.path.exists(ioc_path):
                continue
            # read ioc.ini and get image setting.
            conf = configparser.ConfigParser()
            if conf.read(ioc_path):
                if not conf.get('IOC', 'image'):
                    print(f'gen_compose_files: Warning. Can\'t get image setting of IOC project "{ioc_dir}".')
                    continue
                else:
                    ioc_list.append((ioc_dir, conf.get('IOC', 'image')))
            else:
                print(f'gen_compose_files: Warning. Path "{ioc_path}" is not a valid configuration file.')
                continue

        if not ioc_list:
            print(f'gen_compose_files: Warning. No IOC project found in host directory "{host_dir}".')
        else:
            # yaml file title, name of Compose Project must match pattern '^[a-z0-9][a-z0-9_-]*$'
            yaml_data = {'name': f'ioc-{host_dir}'.lower(), 'services': {}}
            for ioc_data in ioc_list:
                # add services according to IOC projects.
                temp_yaml = {
                    'container_name': ioc_data[0],  # name
                    'image': ioc_data[1],  # image
                    'tty': True,
                    'restart': 'always',
                    'network_mode': 'host',
                    'depends_on': [f'srv-log-{host_dir}', ],
                    'volumes': [
                        {
                            'type': 'bind',
                            'source': f'./{ioc_data[0]}',
                            'target': f'{os.path.join(CONTAINER_IOC_RUN_PATH, ioc_data[0])}',
                        },
                        {
                            'type': 'bind',
                            'source': f'./{LOG_FILE_DIR}',
                            'target': f'{os.path.join(CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR)}',
                        },
                        {
                            'type': 'bind',
                            'source': '/etc/localtime',
                            'target': '/etc/localtime',
                            'read_only': 'true'
                        },  # set correct timezone for linux kernel
                    ],
                    'entrypoint': [
                        'bash',
                        '-c',
                        f'cd RUN/{ioc_data[0]}/startup/iocBoot; ./st.cmd;'
                    ]

                }
                yaml_data['services'].update({f'srv-{ioc_data[0]}': temp_yaml})
            else:
                # add iocLogServer service for host.
                temp_yaml = {
                    'container_name': f'log-{host_dir}',
                    'image': base_image,
                    'tty': True,
                    'restart': 'always',
                    'network_mode': 'host',
                    'volumes': [
                        {
                            'type': 'bind',
                            'source': f'./{os.path.join(LOG_FILE_DIR)}',
                            'target': f'{os.path.join(CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR)}',
                        },
                        {
                            'type': 'bind',
                            'source': '/etc/localtime',
                            'target': '/etc/localtime',
                            'read_only': 'true'
                        },  # set correct timezone for linux kernel
                    ],
                    'entrypoint': [
                        'bash',
                        '-c',
                        f'. ~/.bash_aliases; echo run iocLogServer; iocLogServer'
                        # f'sleep 1h'
                    ],
                    'environment': {
                        'EPICS_IOC_LOG_FILE_NAME':
                            f'{os.path.join(CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR, f"{host_dir}.ioc.log")}',
                    },
                }
                yaml_data['services'].update({f'srv-log-{host_dir}': temp_yaml})
                # make directory for iocLogServer
                try_makedirs(os.path.join(top_path, host_dir, LOG_FILE_DIR))

            # write yaml file
            file_path = os.path.join(top_path, host_dir, 'compose.yaml')
            with open(file_path, 'w') as file:
                yaml.dump(yaml_data, file, default_flow_style=False)
            print(f'gen_compose_files: Create compose file for host "{host_dir}".')
    else:
        print(f'gen_compose_files: Creating compose files Finished.')


# Generate backup file of IOC project settings.
# backup_mode: "src" only copy .ini file and source files; "all" backup all files.
# backup_dir: top dir for BACKUP_DIR.
def repository_backup(backup_mode, backup_dir, verbose):
    ioc_list = get_all_ioc()
    # check whether the setting of IOC projects in snapshot directory are newest and not modified.
    flag = all([ioc_item.check_consistency(run_check=True) for ioc_item in ioc_list])
    if not flag:
        print(f'repository_backup: Failed. Run checks failed.')
        return
    else:
        backup_path = relative_and_absolute_path_to_abs(backup_dir, BACKUP_DIR)  # default in current path ./ioc-backup/
        # collect ioc.ini files and source files into tar.gz file.
        if not os.path.exists(backup_path):
            try_makedirs(backup_path, verbose)
        now_time = datetime.datetime.now().strftime("%Y.%m.%d-%H:%M:%S")
        tar_dir = os.path.join(backup_path, now_time)
        if ioc_list:
            for ioc_item in ioc_list:
                # make temporary directory.
                ioc_tar_dir = os.path.join(tar_dir, ioc_item.name)
                try_makedirs(ioc_tar_dir, verbose)
                # copy entire repository file into tar directory.
                file_copy(ioc_item.config_file_path, os.path.join(ioc_tar_dir, CONFIG_FILE_NAME), mode='rw',
                          verbose=verbose)
                dir_copy(ioc_item.src_path, os.path.join(ioc_tar_dir, 'src'), verbose=verbose)
                if backup_mode == 'all':
                    dir_copy(ioc_item.startup_path, os.path.join(ioc_tar_dir, 'startup'), verbose=verbose)
                    dir_copy(ioc_item.log_path, os.path.join(ioc_tar_dir, 'log'), verbose=verbose)
                    dir_copy(ioc_item.settings_path, os.path.join(ioc_tar_dir, 'settings'), verbose=verbose)
            else:
                with tarfile.open(os.path.join(backup_path, f'{now_time}.tar.gz'), "w:gz") as tar:
                    tar.add(tar_dir, arcname=os.path.basename(tar_dir))
                dir_remove(tar_dir, verbose=verbose)
                print(f'repository_backup: Finished. Backup file created at {backup_path} in "{backup_mode}" mode.')
        else:
            print(f'repository_backup: No IOC project to backup.')


# Restore IOC projects from tgz backup file.
# backup_path: path of the tgz backup file.
# force_overwrite: "True" overwrite existing IOC project if conflicts with the backup file.
# force_overwrite: "False" ask for answer whether to overwrite existing IOC project.
def restore_backup(backup_path, force_overwrite, verbose):
    extract_path = relative_and_absolute_path_to_abs(backup_path)
    if not os.path.isfile(extract_path):
        print(f'restore_backup: Failed. File to extract "{extract_path}" is not exists.')
        return

    # make temporary directory.
    temp_dir = relative_and_absolute_path_to_abs(f'tar_temp_{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}')
    try_makedirs(temp_dir, verbose=verbose)
    # extract tgz files into temporary directory.
    try:
        with tarfile.open(extract_path, 'r:gz') as tar:
            tar.extractall(temp_dir)
    except Exception as e:
        print(f'restore_backup: Failed. Failed to extract "{extract_path}", {e}.')
        dir_remove(temp_dir, verbose=verbose)
        return
    else:
        if verbose:
            print(f'restore_backup: File extracted at {temp_dir}.')
        temp_in_dir = os.path.join(temp_dir, os.listdir(temp_dir)[0])
        print(f'restore_backup: Restoring from backup file "{os.path.basename(temp_in_dir)}".')

    # copy IOC projects. if IOC conflicts, just skip or overwrite.
    ioc_existed = [ioc_item.name for ioc_item in get_all_ioc()]
    for ioc_item in os.listdir(temp_in_dir):
        ioc_dir = os.path.join(temp_in_dir, ioc_item)
        current_path = os.path.join(os.getcwd(), REPOSITORY_DIR, ioc_item)
        if os.path.isdir(ioc_dir) and os.path.exists(os.path.join(ioc_dir, CONFIG_FILE_NAME)):
            if ioc_item not in ioc_existed:
                print(f'restore_backup: Restoring IOC project "{ioc_item}".')
                dir_copy(ioc_dir, current_path, verbose=verbose)
            elif ioc_item in ioc_existed and not force_overwrite:
                while True:
                    ans = input(f'restore_backup: "{ioc_item}" already exists, overwrite '
                                f'it(this will remove the original IOC project files)?[y|n]:')
                    if ans.lower() == 'yes' or ans.lower() == 'y':
                        overwrite_flag = True
                        print(f'restore_backup: choose to overwrite "{ioc_item}".')
                        break
                    elif ans.lower() == 'no' or ans.lower() == 'n':
                        overwrite_flag = False
                        print(f'restore_backup: choose to skip "{ioc_item}".')
                        break
                    else:
                        print(f'restore_backup: wrong input, please enter your answer again.')
                if overwrite_flag:
                    dir_copy(ioc_dir, current_path, verbose=verbose)
            else:
                print(f'restore_backup: Restoring IOC project "{ioc_item}", local project will be deleted.')
                dir_copy(ioc_dir, current_path, verbose=verbose)
        else:
            if verbose:
                print(f'restore_backup: Skip invalid directory "{ioc_item}".')
            continue

    # remove temporary directory finally.
    print(f'restore_backup: Restoring Finished.')
    dir_remove(temp_dir, verbose=verbose)


if __name__ == '__main__':
    # argparse
    parser = argparse.ArgumentParser(description='Manager of IOC projects for docker deploying.')

    subparsers = parser.add_subparsers(
        help='For subparser command help, run "./iocManager.py [create|set|exec|list|remove] -h".')

    #
    parser_create = subparsers.add_parser('create', help='Create IOC projects by given settings.')
    parser_create.add_argument('name', type=str, nargs='+', help='name for IOC project, name list is supported.')
    parser_create.add_argument('-o', '--options', type=str, nargs='+',
                               help='manually specify attributes in ioc.ini file, format: "key=value". attributes set '
                                    'by this option will override other options if conflicts.')
    parser_create.add_argument('-s', '--section', type=str, default='IOC',
                               help='specify section used for manually specified attributes. default section "IOC".')
    parser_create.add_argument('-f', '--ini-file', type=str,
                               help='copy settings from specified .ini files. attributes set by this '
                                    'option may be override by other options.')
    parser_create.add_argument('--caputlog', action="store_true", help='add caPutLog module.')
    parser_create.add_argument('--status-ioc', action="store_true",
                               help='add devIocStats module for IOC monitor.')
    parser_create.add_argument('--status-os', action="store_true",
                               help='add devIocStats module for OS monitor.')
    parser_create.add_argument('--autosave', action="store_true", help='add autosave module.')
    parser_create.add_argument('--add-asyn', action="store_true",
                               help='add asyn template. set "--port-type" to choose port type, default "tcp/ip".')
    parser_create.add_argument('--add-stream', action="store_true",
                               help='add StreamDevice template. '
                                    'set "--port-type" to choose port type, default "tcp/ip".')
    parser_create.add_argument('--port-type', type=str, default='tcp/ip',
                               help='specify port type. choose from "tcp/ip"(default) or "serial".')
    parser_create.add_argument('--add-raw', action="store_true",
                               help='add raw command template in .ini file, so to add custom commands in .ini file.')
    parser_create.add_argument('-p', '--print-ioc', action="store_true", help='print settings of created IOC projects.')
    parser_create.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_create.set_defaults(func='parse_create')

    #
    parser_set = subparsers.add_parser('set', help='Set attributes for IOC projects.')
    parser_set.add_argument('name', type=str, nargs='+', help='name for IOC project, name list is supported.')
    parser_set.add_argument('-o', '--options', type=str, nargs='+',
                            help='manually specify attributes in ioc.ini file, format: "key=value". attributes set '
                                 'by this option will override other options if conflicts.')
    parser_set.add_argument('-s', '--section', type=str, default='IOC',
                            help='specify section used for manually specified attributes. default section "IOC".')
    parser_set.add_argument('-f', '--ini-file', type=str,
                            help='copy settings from specified .ini files. attributes set by this '
                                 'option may be override by other options.')
    parser_set.add_argument('--caputlog', action="store_true", help='add caPutLog module.')
    parser_set.add_argument('--status-ioc', action="store_true",
                            help='add devIocStats module for IOC monitor.')
    parser_set.add_argument('--status-os', action="store_true",
                            help='add devIocStats module for OS monitor.')
    parser_set.add_argument('--autosave', action="store_true", help='add autosave module.')
    parser_set.add_argument('--add-asyn', action="store_true",
                            help='add asyn template. set "--port-type" to choose port type, default "tcp/ip".')
    parser_set.add_argument('--add-stream', action="store_true",
                            help='add StreamDevice template. '
                                 'set "--port-type" to choose port type, default "tcp/ip".')
    parser_set.add_argument('--port-type', type=str, default='tcp/ip',
                            help='specify port type. choose from "tcp/ip"(default) or "serial".')
    parser_set.add_argument('--add-raw', action="store_true",
                            help='add raw command template in .ini file, so to add custom commands in .ini file.')
    parser_set.add_argument('-p', '--print-ioc', action="store_true", help='print settings of modified IOC projects.')
    parser_set.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_set.set_defaults(func='parse_set')

    #
    parser_execute = subparsers.add_parser('exec', help='Execute functions for IOC projects.')
    parser_execute.add_argument('name', type=str, nargs='*', help='name for IOC project, a name list is supported.')
    # Sort by operation procedure.
    parser_execute.add_argument('-a', '--add-src-file', action="store_true",
                                help='add source files from given path and update settings. '
                                     'set "--src-path" to choose a path to find the source files.')
    parser_execute.add_argument('--src-path', type=str, default='',
                                help='path where to find source files. default the "src" folder '
                                     'in the IOC project directory structure.')
    parser_execute.add_argument('-s', '--gen-startup-file', action="store_true",
                                help='generate st.cmd file and the other startup files for IOC running in container. '
                                     'set "--force-silent" to force silent running. '
                                     'set "--force-default" to use default settings.')
    parser_execute.add_argument('--force-silent', action="store_true",
                                help='force silent while generating startup files.')
    parser_execute.add_argument('--force-default', action="store_true",
                                help='use default when generating startup files.')
    parser_execute.add_argument('-e', '--export-for-mount', action="store_true",
                                help='export runtime files of specified IOC projects into a mount dir. '
                                     'set "--mount-path" to choose a top path for mount dir. '
                                     'set "--force-overwrite" to enable overwrite when IOC in mount dir '
                                     'conflicts with the one in repository. ')
    parser_execute.add_argument('--mount-path', type=str, default='..',
                                help=f'top path for mount dir, dir "{MOUNT_DIR}" would be created here if not exists. '
                                     f'default the upper directory "../".')
    parser_execute.add_argument('--force-overwrite', action="store_true", default=False,
                                help='force overwrite if the IOC project already exists.')
    parser_execute.add_argument('-c', '--gen-compose-file', action="store_true",
                                help='generate Docker Compose file for all hosts and IOC projects in mount directory. '
                                     'set "--mount-path" to select a top path to find mount dir. '
                                     'set "--base-image" to choose a base image uesd for running iocLogserver.')
    parser_execute.add_argument('--base-image', type=str, default='base:dev',
                                help='base image used for running iocLogserver. default "base:dev".')
    parser_execute.add_argument('-b', '--gen-backup-file', action="store_true",
                                help='generate backup file of all IOC projects, all IOC projects in repository will be '
                                     'packed and compressed into a tgz file. '
                                     'set "--backup-path" to choose a backup directory. '
                                     'set "--backup-mode" to choose a backup mode.')
    parser_execute.add_argument('--backup-path', type=str, default='../ioc-backup',
                                help='dir path used for storing backup files of IOC projects. default "../ioc-backup".')
    parser_execute.add_argument('--backup-mode', type=str, default='src',
                                help='backup mode for IOC projects. "all": back up all files including running files'
                                     '(files generated by autosave, etc.). "src": just back up files of IOC '
                                     'settings and source files. default "src" mode.')
    parser_execute.add_argument('-r', '--restore-backup-file', action="store_true",
                                help='restore IOC projects from tgz backup file. set "--backup-path" to choose a backup'
                                     'directory. set "--force-overwrite" to enable overwrite when IOC in backup file '
                                     'conflicts with the one in repository.')
    parser_execute.add_argument('--backup-file', type=str, default='',
                                help='tgz backup file of IOC projects. format "../ioc-backup/file".')
    parser_execute.add_argument('--run-check', action="store_true",
                                help='execute run-check for all IOC projects.')
    parser_execute.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_execute.set_defaults(func='parser_execute')

    #
    parser_list = subparsers.add_parser('list', help='List existing IOC projects filtered by given conditions.')
    parser_list.add_argument('condition', type=str, nargs='*',
                             help='conditions to filter IOC projects in specified section. format: "xxx=xxx". '
                                  'list all IOC projects if no condition provided.')
    parser_list.add_argument('-s', '--section', type=str, default='IOC',
                             help='specify a section applied for condition filtering. default section: "IOC".')
    parser_list.add_argument('-l', '--ioc-list', type=str, nargs='*',
                             help='from a IOC list to filter IOC projects by given conditions.')
    parser_list.add_argument('-i', '--show-info', action="store_true", help='show details of IOC settings.')
    parser_list.add_argument('-r', '--raw-info', action="store_true", help='show IOC settings in raw format.')
    parser_list.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_list.set_defaults(func='parse_list')

    #
    parser_remove = subparsers.add_parser('remove', help='Remove IOC projects.')
    parser_remove.add_argument('name', type=str, nargs='+', help='name for IOC project, name list is supported.')
    parser_remove.add_argument('-r', '--remove-all', action="store_true",
                               help='enable this option will delete the entire IOC project!')
    parser_remove.add_argument('-f', '--force', action="store_true", help='force removal, do not ask.')
    parser_remove.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_remove.set_defaults(func='parse_remove')

    args = parser.parse_args()
    if not any(vars(args).values()):
        parser.print_help()
        exit()

    # print(f'{args}')
    if args.verbose:
        print(args)
    if args.func == 'parse_create' or args.func == 'parse_set':
        conf_temp = configparser.ConfigParser()
        #
        if args.ini_file:
            if conf_temp.read(args.ini_file):
                print(f'Read .ini file "{args.ini_file}".')
            else:
                print(f'Read failed, invalid .ini file "{args.ini_file}", skipped.')
        #
        module_installed = ''
        if args.autosave:
            module_installed += 'autosave, '
        if args.caputlog:
            module_installed += 'caputlog, '
        if args.status_ioc:
            module_installed += 'status-ioc, '
        if args.status_os:
            module_installed += 'status-os, '
        module_installed = module_installed.rstrip(', ')
        if module_installed:
            if not conf_temp.has_section('IOC'):
                conf_temp.add_section('IOC')
            conf_temp.set('IOC', 'module', module_installed)
            if args.verbose:
                print(f'Set "module : {module_installed}" by specified options.')
        #
        if args.options:
            args.section = args.section.upper()
            if not conf_temp.has_section(args.section):
                conf_temp.add_section(args.section)
            for item in args.options:
                k, v = condition_parse(item, 1)
                if k:
                    conf_temp.set(args.section, k, v)
                    if args.verbose:
                        print(f'Set "{k}: {v}" for section "{args.section}".')
                else:
                    if args.verbose:
                        print(f'Invalid option "{item}" specified for section "{args.section}", skipped.')
        #
        if args.func == 'parse_create':
            # ./iocManager.py create
            create_ioc(args.name, args, config=conf_temp, verbose=args.verbose)
        else:
            # ./iocManager.py set
            for item in args.name:
                set_ioc(item, args, config=conf_temp, verbose=args.verbose)
    if args.func == 'parse_list':
        # ./iocManager.py list
        get_filtered_ioc(args.condition, section=args.section, from_list=args.ioc_list, raw_info=args.raw_info,
                         show_info=args.show_info, verbose=args.verbose)
    if args.func == 'parse_remove':
        # ./iocManager.py remove
        for item in args.name:
            remove_ioc(item, all_remove=args.remove_all, force_removal=args.force, verbose=args.verbose)
    if args.func == 'parser_execute':
        # ./iocManager.py exec
        execute_ioc(args)
