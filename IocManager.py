#!/usr/bin/python3
import argparse
import configparser
import os
from collections.abc import Iterable

from imtools.IMFuncsAndConst import (try_makedirs, dir_copy, condition_parse,
                                     MOUNT_DIR, REPOSITORY_DIR, CONFIG_FILE_NAME)
from imtools.IocClass import IOC


# accepts iterable for input
def create_ioc(name, args, config=None, verbose=False):
    if isinstance(name, str):
        # may add a name string filter here?
        dir_path = os.path.join(os.getcwd(), REPOSITORY_DIR, name)
        if os.path.exists(os.path.join(dir_path, CONFIG_FILE_NAME)):
            print(f'create_ioc: Failed. IOC "{name}" already exists.')
        else:
            # create an IOC and do initialization by given configparser.ConfigParser() object.
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
                        if section == 'IOC' and option == 'name':
                            continue
                        value = config.get(section, option)
                        ioc_temp.set_config(option, value, section)
                ioc_temp.set_config('status', 'unready')
            print(f'create_ioc: Success. IOC "{name}" created.')
            ioc_temp.check_consistency()
            if args.print_ioc:
                ioc_temp.show_config()
    elif isinstance(name, Iterable):
        for n in name:
            create_ioc(n, args, config, verbose)
    else:
        print(f'create_ioc: Failed. Invalid input args: "{name}".')


# do not accept iterable for input
def set_ioc(name, args, config=None, verbose=False):
    if isinstance(name, str):
        dir_path = os.path.join(os.getcwd(), REPOSITORY_DIR, name)
        if os.path.exists(os.path.join(dir_path, CONFIG_FILE_NAME)):
            # initialize an existing IOC, edit ioc.ini by given configparser.ConfigParser() object.
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
                    print(f'set_ioc: No config given for setting IOC "{name}".')
        else:
            print(f'set_ioc: Failed. IOC "{name}" is not exists.')
    else:
        print(f'set_ioc: Failed. Invalid input args "{name}".')


# remove only generated files or remove all, do not accept iterable for input.
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
                print(f'remove_ioc: Success. IOC "{name}" removed, src/" directory and "ioc.ini" file preserved.')
    else:
        print(f'remove_ioc: Failed. IOC "{name}" not found.')


# do nothing, just create an IOC() object by given path to activate its self.__init__() for a name check scheme.
def refresh_ioc(name):
    if isinstance(name, str):
        # may add a name string filter here.
        dir_path = os.path.join(os.getcwd(), REPOSITORY_DIR, name)
        if os.path.exists(os.path.join(dir_path, CONFIG_FILE_NAME)):
            IOC(dir_path)
    elif isinstance(name, Iterable):
        for n in name:
            refresh_ioc(n)


# show all subdirectory IOCs for given path, return the list of all IOCs.
def get_all_ioc(dir_path=None, from_list=None):
    ioc_list = []
    if not dir_path:
        dir_path = os.path.join(os.getcwd(), REPOSITORY_DIR)

    # sort according to name.
    items = os.listdir(dir_path)
    if from_list:
        temp_items = []
        for i in items:
            if i in from_list:
                temp_items.append(i)
        else:
            items = temp_items
    items.sort()
    for p in items:
        subdir_path = os.path.join(dir_path, p)
        if os.path.isdir(subdir_path) and CONFIG_FILE_NAME in os.listdir(subdir_path):
            ioc_list.append(IOC(subdir_path))
    return ioc_list


# show IOC for specified conditions of specified section, AND logic was implied to each condition.
def get_filtered_ioc(condition: Iterable, section='IOC', from_list=None, show_info=False, verbose=False):
    ioc_list = get_all_ioc(from_list=from_list)
    if from_list is not None:
        print(f'List from given list "{from_list}":')

    section = section.upper()  # to support case-insensitive filter.

    index_to_remove = []
    if not condition:
        # default not filter any IOC by options, but filter by sections.
        for i in range(0, len(ioc_list)):
            if not ioc_list[i].conf.has_section(section=section):
                index_to_remove.append(i)
        if verbose:
            print(f'No condition specified, list IOC that with section "{section}":')
    elif isinstance(condition, str):
        key, value = condition_parse(condition)
        if key:
            for i in range(0, len(ioc_list)):
                if not ioc_list[i].check_config(key, value, section):
                    index_to_remove.append(i)
            if verbose:
                print(f'Results for "{condition}" in section "{section}":')
        else:
            # wrong condition parsed, not return any result.
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
                    print(f'Invalid condition "{c}" specified, skipped.')
        if valid_flag:
            # if there is any valid condition given, not return any result.
            if verbose:
                print(f'Results for conditions "{valid_condition}" in section "{section}":')
        else:
            # if there is no valid condition given, show.
            index_to_remove = [i for i in range(0, len(ioc_list))]
            if verbose:
                print(f'No result. No valid condition specified: "{condition}".')
    else:
        index_to_remove = [i for i in range(0, len(ioc_list))]
        if verbose:
            print(f'No result. No valid condition specified: "{condition}".')

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


def execute_ioc(name, args):
    dir_path = os.path.join(os.getcwd(), REPOSITORY_DIR, name)
    if os.path.exists(os.path.join(dir_path, CONFIG_FILE_NAME)):
        ioc_temp = IOC(dir_path, args.verbose)
        if args.add_src_files:
            ioc_temp.get_src_file(args.src_path)
        elif args.run_check:
            ioc_temp.check_consistency(run_check=True)
        elif args.gen_st_cmd:
            ioc_temp.generate_st_cmd(force_executing=args.force_silent, force_default=args.force_default)
        elif args.to_docker:
            repository_to_container(item, args.mount_path, args.verbose)
        else:
            print(f'execute_ioc: No "exec" option specified for IOC "{name}".')
    else:
        print(f'execute_ioc: Failed. IOC "{name}" not found.')


# generate directory structure for running inside the container.
def repository_to_container(name, mount_path=None, verbose=False):
    dir_path = os.path.join(os.getcwd(), REPOSITORY_DIR, name)
    if os.path.exists(os.path.join(dir_path, CONFIG_FILE_NAME)):
        ioc_temp = IOC(dir_path, verbose)

        if not ioc_temp.check_config('status', 'ready'):
            print(f'repository_to_container: Failed. Option "status" in IOC "{ioc_temp.name}" is not '
                  f'"ready", you should first generate startup files before executing this command.')
            return

        container_name = ioc_temp.get_config('container')
        if not container_name:
            container_name = ioc_temp.name
            if verbose:
                print(f'repository_to_container: Option "container" not defined in IOC "{ioc_temp.name}", '
                      f'automatically use IOC name as container name.')
        host_name = ioc_temp.get_config('host')
        if not host_name:
            host_name = 'localhost'
            if verbose:
                print(f'repository_to_container: Option "host" not defined in IOC "{ioc_temp.name}", '
                      f'automatically use "localhost" as host name.')
        if not mount_path:
            mount_path = os.getcwd()
            if verbose:
                print(f'repository_to_container: Argument "mount_path" not given, '
                      f'automatically use current work directory as generate path.')
        else:
            if not os.path.isabs(mount_path):
                mount_path = os.path.abspath(mount_path)
        if not os.path.isdir(mount_path):
            print(f'repository_to_container: Failed. Invalid argument "mount_path".')
            return
        else:
            top_path = os.path.join(mount_path, MOUNT_DIR, host_name, container_name)
            if dir_copy(ioc_temp.dir_path, top_path, verbose):
                print(f'repository_to_container: Success. IOC "{name}" directory created in mount path for docker.')
            else:
                print(f'repository_to_container: Failed. You may run this command again using "-v" option to see '
                      f'what happened for IOC "{name}" in details.')
    else:
        print(f'repository_to_container: Failed. IOC "{name}" not found.')


# Collect files from the container directory to central repository LOG directory.
def container_to_repository(container_path, repository_LOG_path):
    pass


if __name__ == '__main__':
    # argparse
    parser = argparse.ArgumentParser(description='IOC project manager for docker. This script should be run inside'
                                                 ' the repository directory, where there exists an "imtools" folder.')

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
                               help='specify port type used for asyn or StreamDevice.')
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
                            help='specify port type used for asyn or StreamDevice.')
    parser_set.add_argument('--add-raw', action="store_true", help='add raw command template.')
    parser_set.add_argument('-p', '--print-ioc', action="store_true", help='print settings of modified IOC projects.')
    parser_set.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_set.set_defaults(func='parse_set')

    #
    parser_execute = subparsers.add_parser('exec', help='Execute functions for IOC projects.')
    parser_execute.add_argument('name', type=str, nargs='+', help='name for IOC project, a name list is supported.')
    parser_execute.add_argument('-s', '--add-src-files', action="store_true",
                                help='add source files from given path.')
    parser_execute.add_argument('--src-path', type=str, default='',
                                help='specify a path from where get source files, default  the "src/" directory of '
                                     'the IOC project itself.')
    parser_execute.add_argument('-c', '--run-check', action="store_true",
                                help='execute run check to enable "--gen-st-cmd" option.')
    parser_execute.add_argument('-g', '--gen-st-cmd', action="store_true",
                                help='generate st.cmd file and other startup files.')
    parser_execute.add_argument('--force-silent', action="store_true",
                                help='force silent when running "--gen-st-cmd" option, do not ask for confirmation.')
    parser_execute.add_argument('--force-default', action="store_true",
                                help='using default when running "--gen-st-cmd" option.')
    parser_execute.add_argument('-o', '--to-docker', action="store_true",
                                help='copy run-time files of generated IOC projects out to a path for docker mounting.')
    parser_execute.add_argument('--mount-path', type=str, default='',
                                help='specify a mount path where all the generated run-time files go into, '
                                     'default current work path.')
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
        get_filtered_ioc(args.condition, section=args.section, from_list=args.from_list, show_info=args.show_info,
                         verbose=args.verbose)
    if args.func == 'parse_remove':
        for item in args.name:
            remove_ioc(item, all_remove=args.remove_all, force_removal=args.force, verbose=args.verbose)
    if args.func == 'parser_execute':
        for item in args.name:
            execute_ioc(item, args)
