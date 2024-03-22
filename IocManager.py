#!/usr/bin/python3
import argparse
import configparser
import yaml
import os
import datetime
import tarfile
from collections.abc import Iterable

from imtools.IMFuncsAndConst import (try_makedirs, dir_copy, file_copy, condition_parse, dir_remove,
                                     relative_and_absolute_path_to_abs,
                                     MOUNT_DIR, REPOSITORY_DIR, CONFIG_FILE_NAME, CONTAINER_IOC_RUN_PATH, LOG_FILE_DIR,
                                     BACKUP_DIR)
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
            if args.add_stream:
                ioc_temp.add_stream_template(args.port_type)
            if args.add_raw:
                ioc_temp.add_raw_cmd_template()
            if config:
                for section in config.sections():
                    for option in config.options(section):
                        if section == 'IOC' and option == 'name':  # Name should not be modified.
                            continue
                        value = config.get(section, option)
                        ioc_temp.set_config(option, value, section)
                ioc_temp.set_config('status', 'unready')  # Status 'ready' should not be copied.
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
            if args.add_stream:
                ioc_temp.add_stream_template(args.port_type)
                modify_flag = True
            if args.add_raw:
                ioc_temp.add_raw_cmd_template()
                modify_flag = True
            if any(config.options(section) for section in config.sections()):
                for section in config.sections():
                    for option in config.options(section):
                        if section == 'IOC' and option == 'name':
                            continue
                        value = config.get(section, option)
                        ioc_temp.set_config(option, value, section)
                ioc_temp.set_config('status', 'unready')
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
def get_filtered_ioc(condition: Iterable, section='IOC', from_list=None, show_info=False, verbose=False):
    section = section.upper()  # to support case-insensitive filter for section.

    ioc_list = get_all_ioc(from_list=from_list)
    if from_list is not None:
        print(f'Search IOC projects from list "{from_list}":')

    index_to_remove = []
    if not condition:
        # Filter IOC projects by not having specified section when no condition is specified.
        # Default will return all IOC projects, because all IOC projects have section "IOC".
        for i in range(0, len(ioc_list)):
            if not ioc_list[i].conf.has_section(section=section):
                index_to_remove.append(i)
        if verbose:
            print(f'No condition specified, list IOC projects that with section "{section}":')
    elif isinstance(condition, str):
        key, value = condition_parse(condition)
        if key:
            for i in range(0, len(ioc_list)):
                if not ioc_list[i].check_config(key, value, section):
                    index_to_remove.append(i)
            if verbose:
                print(f'Results for section "{section}" and condition "{condition}":')
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
                for i in range(0, len(ioc_list)):
                    if not ioc_list[i].check_config(key, value, section):
                        index_to_remove.append(i)
            else:
                if verbose:
                    print(f'Skipped invalid condition "{c}".')
        if valid_flag:
            if verbose:
                print(f'Results for conditions section "{section}" and "{valid_condition}":')
        else:
            # Do not return any result, if there is no valid condition given.
            index_to_remove = [i for i in range(0, len(ioc_list))]
            if verbose:
                print(f'No result. No valid condition specified: "{condition}".')
    else:
        index_to_remove = [i for i in range(0, len(ioc_list))]  # remove all
        if verbose:
            print(f'No result. Invalid condition: "{condition}".')

    index_to_preserve = []
    for i in range(0, len(ioc_list)):
        if i in index_to_remove:
            continue
        else:
            index_to_preserve.append(i)
    for i in index_to_preserve:
        if show_info:
            ioc_list[i].show_config()
        else:
            print(ioc_list[i].name, end=' ')
    else:
        print('')

    for i in index_to_preserve:
        ioc_list[i].check_consistency()


def execute_ioc(args):
    # operation for all IOC projects.
    if args.gen_compose_file:
        gen_compose_files(base_image=args.base, mount_dir=args.mount_path, verbose=args.verbose)
    elif args.gen_backup:
        repository_backup(backup_mode=args.backup_mode, backup_dir=args.backup_path, verbose=args.verbose)
    else:
        # operation for specific IOC projects.
        if not args.name:
            print(f'execute_ioc: No IOC project was specified.')
        else:
            for name in args.name:
                dir_path = os.path.join(os.getcwd(), REPOSITORY_DIR, name)
                if os.path.exists(os.path.join(dir_path, CONFIG_FILE_NAME)):
                    ioc_temp = IOC(dir_path, args.verbose)
                    if args.add_src_files:
                        ioc_temp.get_src_file(src_dir=args.src_path)
                    elif args.gen_st_cmd:
                        ioc_temp.generate_st_cmd(force_executing=args.force_silent, force_default=args.force_default)
                    elif args.run_check:
                        ioc_temp.check_consistency(run_check=True)
                    elif args.out_to_docker:
                        repository_to_container(name, mount_dir=args.mount_path,
                                                force_overwrite=args.force_overwrite, verbose=args.verbose)
                    else:
                        print(f'execute_ioc: No "exec" option specified for IOC "{name}".')
                else:
                    print(f'execute_ioc: Failed. IOC "{name}" not found.')


# Generate directory structure of an IOC project for running inside the container.
def repository_to_container(name, mount_dir=None, force_overwrite=False, verbose=False):
    dir_path = os.path.join(os.getcwd(), REPOSITORY_DIR, name)
    if os.path.exists(os.path.join(dir_path, CONFIG_FILE_NAME)):
        ioc_temp = IOC(dir_path, verbose)

        if not ioc_temp.check_consistency(run_check=True):
            print(f'repository_to_container: Failed. All run checks should be passed before executing this command.')
            return

        container_name = ioc_temp.get_config('container')
        host_name = ioc_temp.get_config('host')
        if not container_name:
            container_name = ioc_temp.name
            if verbose:
                print(f'repository_to_container: Option "container" not defined in IOC "{ioc_temp.name}", '
                      f'automatically use IOC name as container name.')
        if not host_name:
            host_name = 'localhost'
            if verbose:
                print(f'repository_to_container: Option "host" not defined in IOC "{ioc_temp.name}", '
                      f'automatically use "localhost" as host name.')
        mount_path = relative_and_absolute_path_to_abs(mount_dir, '..')
        if not os.path.isdir(mount_path):
            print(f'repository_to_container: Failed. Argument "mount_path: {mount_path}" is not a directory.')
            return
        top_path = os.path.join(mount_path, MOUNT_DIR, host_name, container_name)
        if not os.path.isdir(top_path) or force_overwrite:
            if dir_copy(ioc_temp.dir_path, top_path, verbose):
                print(f'repository_to_container: Success. IOC "{name}" directory created in {mount_path}.')
                # set readonly permission.
                os.chmod(os.path.join(top_path, 'ioc.ini'), mode=0o444)
            else:
                print(f'repository_to_container: Failed. You may run this command again with "-v" option to see '
                      f'what happened for IOC "{name}" in details.')
        elif os.path.isdir(top_path):
            file_to_copy = ('ioc.ini',)
            dir_to_copy = ('settings', 'src', 'startup',)
            for item in file_to_copy:
                file_copy(os.path.join(ioc_temp.dir_path, item), os.path.join(top_path, item), verbose=verbose)
            for item in dir_to_copy:
                if not dir_copy(os.path.join(ioc_temp.dir_path, item), os.path.join(top_path, item), verbose):
                    print(f'repository_to_container: Failed. You may run this command again with "-v" option to see '
                          f'what happened for IOC "{name}" in details.')
                    return
            else:
                print(f'repository_to_container: Success. IOC "{name}" directory updated in {mount_path}.')
    else:
        print(f'repository_to_container: Failed. IOC "{name}" not found.')


# Generate Docker Compose file for all hosts and IOC projects in given path.
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

            if verbose:
                print(f'gen_compose_files: Create compose file for host "{host_dir}".')
            # write yaml file
            file_path = os.path.join(top_path, host_dir, 'compose.yaml')
            with open(file_path, 'w') as file:
                yaml.dump(yaml_data, file, default_flow_style=False)


# Generate backup file of IOC project settings.
def repository_backup(backup_mode, backup_dir, verbose):
    # check setting of IOC projects in .log/ directory are newest and not modified.
    ioc_list = get_all_ioc()
    flag = all([ioc_item.check_consistency() for ioc_item in ioc_list])
    if not flag:
        print(f'repository_backup: Failed. Normal checks failed for all IOC project.')
        return
    else:
        backup_path = relative_and_absolute_path_to_abs(backup_dir, BACKUP_DIR)
        # collect ioc.ini files and source files into tar.gz file.
        if not os.path.exists(backup_path):
            try_makedirs(backup_path, verbose)
        now_time = datetime.datetime.now().strftime("%Y.%m.%d-%H:%M:%S")
        tar_dir = os.path.join(backup_path, now_time)
        for ioc_item in ioc_list:
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
            print(f'repository_backup: Finished. Backup files created at {backup_path} in "{backup_mode}" mode.')


# Restore IOC projects from backup file.
def backup_restore(backup_dir, verbose):
    # restore IOC projects form tar.gz file.
    pass


if __name__ == '__main__':
    # argparse
    parser = argparse.ArgumentParser(description='Manager of IOC projects for docker.')

    subparsers = parser.add_subparsers(
        help='For subparser command help, run "./iocManager.py [create|set|exec|list|remove] -h".')

    #
    parser_create = subparsers.add_parser('create', help='Create IOC projects by given settings.')
    parser_create.add_argument('name', type=str, nargs='+', help='name for IOC project, a name list is supported.')
    parser_create.add_argument('-f', '--ini-file', type=str,
                               help='copy settings from specified .ini files, attributes set by this '
                                    'option may be override by other options.')
    parser_create.add_argument('-o', '--options', type=str, nargs='+',
                               help='manually specify attributes in ioc.ini, format:"key=value". settings set by '
                                    'this option will override other options if conflicts.')
    parser_create.add_argument('-s', '--section', type=str, default='IOC',
                               help='specify section used for manually specified attributes, default section:"IOC".')
    parser_create.add_argument('--caputlog', action="store_true", help='add caPutLog module.')
    parser_create.add_argument('--status-ioc', action="store_true",
                               help='add devIocStats module for IOC monitor.')
    parser_create.add_argument('--status-os', action="store_true",
                               help='add devIocStats module for OS monitor.')
    parser_create.add_argument('--autosave', action="store_true", help='add autosave module.')
    parser_create.add_argument('--add-asyn', action="store_true", help='add asyn template.')
    parser_create.add_argument('--add-stream', action="store_true", help='add StreamDevice template.')
    parser_create.add_argument('--port-type', type=str, default='tcp/ip',
                               help='specify port type used for "--add-asyn" or "--add-stream".')
    parser_create.add_argument('--add-raw', action="store_true", help='add raw command template.')
    parser_create.add_argument('-p', '--print-ioc', action="store_true", help='print settings of created IOC projects.')
    parser_create.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_create.set_defaults(func='parse_create')

    #
    parser_set = subparsers.add_parser('set', help='Set attributes for IOC projects.')
    parser_set.add_argument('name', type=str, nargs='+', help='name for IOC project, a name list is supported.')
    parser_set.add_argument('-f', '--ini-file', type=str,
                            help='copy settings from specified .ini files, attributes set by this '
                                 'option may be override by other options.')
    parser_set.add_argument('-o', '--options', type=str, nargs='+',
                            help='manually specify attributes in ioc.ini, format:"key=value". settings set by '
                                 'this option will override other options if conflicts.')
    parser_set.add_argument('-s', '--section', type=str, default='IOC',
                            help='specify section used for manually specified attributes, default section:"IOC".')
    parser_set.add_argument('--caputlog', action="store_true", help='add caPutLog module.')
    parser_set.add_argument('--status-ioc', action="store_true",
                            help='add devIocStats module for IOC monitor.')
    parser_set.add_argument('--status-os', action="store_true",
                            help='add devIocStats module for OS monitor.')
    parser_set.add_argument('--autosave', action="store_true", help='add autosave module.')
    parser_set.add_argument('--add-asyn', action="store_true", help='add asyn template.')
    parser_set.add_argument('--add-stream', action="store_true", help='add StreamDevice template.')
    parser_set.add_argument('--port-type', type=str, default='tcp/ip',
                            help='specify port type used for "--add-asyn" or "--add-stream".')
    parser_set.add_argument('--add-raw', action="store_true", help='add raw command template.')
    parser_set.add_argument('-p', '--print-ioc', action="store_true", help='print settings of modified IOC projects.')
    parser_set.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_set.set_defaults(func='parse_set')

    #
    parser_execute = subparsers.add_parser('exec', help='Execute functions for IOC projects.')
    parser_execute.add_argument('name', type=str, nargs='*', help='name for IOC project, a name list is supported.')
    parser_execute.add_argument('-a', '--add-src-files', action="store_true",
                                help='from given path add source files and update settings. '
                                     'set "--src-path" to choose a path.')
    parser_execute.add_argument('--src-path', type=str, default='',
                                help='path where to get source files. default the "src" directory in the IOC project.')
    parser_execute.add_argument('-c', '--run-check', action="store_true", help='execute run-checks.')
    parser_execute.add_argument('-d', '--gen-compose-file', action="store_true",
                                help='generate Docker Compose file for all hosts and IOC projects. set "--mount-path" '
                                     'to select a mount top path. set "--base" to choose base image for iocLogserver.')
    parser_execute.add_argument('--base', type=str, default='base:dev',
                                help='base image used for running iocLogserver. default "base:dev".')
    parser_execute.add_argument('--mount-path', type=str, default='..',
                                help='top path of mount path. default the upper directory "../".')
    parser_execute.add_argument('-o', '--out-to-docker', action="store_true",
                                help='copy run-time files of all generated IOC projects into a mount path for docker. '
                                     'set "--mount-path" to choose a top path for mounting. ')
    parser_execute.add_argument('--force-overwrite', action="store_true", default=False,
                                help='force overwrite if the IOC project already exists '
                                     'in the mount path, this will delete all files that are generated during running.')
    parser_execute.add_argument('-s', '--gen-st-cmd', action="store_true",
                                help='generate st.cmd file and the other startup files. set "--force-silent" to force '
                                     'silent running. set "--force-default" to use default settings.')
    parser_execute.add_argument('--force-silent', action="store_true",
                                help='force silent while generating startup files.')
    parser_execute.add_argument('--force-default', action="store_true",
                                help='use default when generating startup files.')
    parser_execute.add_argument('-b', '--gen-backup', action="store_true",
                                help='generate backup files of all IOC projects. set "--backup-path" to choose a backup'
                                     'directory. set "--backup-mode" to choose a backup mode.')
    parser_execute.add_argument('--backup-path', type=str, default='../ioc-backup',
                                help='path used for backup files of IOC projects. default "../ioc-backup".')
    parser_execute.add_argument('--backup-mode', type=str, default='src',
                                help='backup mode for IOC projects. "all": back up all files including running files'
                                     '(such as files generated by autosave, etc). "src": just back up files of IOC '
                                     'settings and source files. default "src".')
    parser_execute.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_execute.set_defaults(func='parser_execute')

    #
    parser_list = subparsers.add_parser('list', help='Get existing IOC projects by given conditions.')
    parser_list.add_argument('condition', type=str, nargs='*',
                             help='conditions to filter IOC, list all IOC if no input provided.')
    parser_list.add_argument('-s', '--section', type=str, default='IOC',
                             help='appointing a section for filter, default section: "IOC".')
    parser_list.add_argument('-l', '--from-list', type=str, nargs='*',
                             help='get IOC by given conditions form given IOC list.')
    parser_list.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_list.add_argument('-i', '--show-info', action="store_true", help='show details of IOC.')
    parser_list.set_defaults(func='parse_list')

    #
    parser_remove = subparsers.add_parser('remove', help='Remove IOC projects.')
    parser_remove.add_argument('name', type=str, nargs='+', help='name for IOC project, a name list is supported.')
    parser_remove.add_argument('-r', '--remove-all', action="store_true",
                               help='remove the entire IOC project, be caution to use this option!.')
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
                print(f'Set "module : {module_installed}" according to specified options for section "IOC".')
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
                        print(f'Wrong option "{item}" from specified options for section "{args.section}", '
                              f'skipped.')
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
        get_filtered_ioc(args.condition, section=args.section, from_list=args.from_list, show_info=args.show_info,
                         verbose=args.verbose)
    if args.func == 'parse_remove':
        # ./iocManager.py remove
        for item in args.name:
            remove_ioc(item, all_remove=args.remove_all, force_removal=args.force, verbose=args.verbose)
    if args.func == 'parser_execute':
        # ./iocManager.py exec
        execute_ioc(args)
