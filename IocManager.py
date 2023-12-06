#!/usr/bin/python3
import argparse
import configparser
import os
from collections.abc import Iterable

from imtools.IMFuncsAndConst import try_makedirs, dir_copy, condition_parse
from imtools.IocClass import IOC, REPOSITORY_TOP, CONFIG_FILE


# accepts iterable for input
def create_ioc(name, verbose=False, config=None):
    if isinstance(name, str):
        # may add a name string filter here.
        dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name)
        if os.path.exists(os.path.join(dir_path, CONFIG_FILE)):
            print(f'create_ioc: failed, IOC "{name}" already exists.')
        else:
            # create an IOC and do initialization by given configparser.ConfigParser() object.
            try_makedirs(dir_path, verbose)
            ioc_temp = IOC(dir_path, verbose)
            if config:
                for section in config.sections():
                    for option in config.options(section):
                        value = config.get(section, option)
                        ioc_temp.set_config(option, value, section)
            print(f'create_ioc: success, IOC "{name}" created.')
            ioc_temp.check_consistency(in_container=False)
            if verbose:
                ioc_temp.show_config()
    elif isinstance(name, Iterable):
        for n in name:
            create_ioc(n, verbose, config)
    else:
        print(f'create_ioc: failed, invalid input args: "{name}".')


# do not accept iterable for input
def set_ioc(name, verbose=False, config=None):
    if isinstance(name, str):
        dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name)
        if os.path.exists(os.path.join(dir_path, CONFIG_FILE)):
            # initialize an existing IOC, edit ioc.ini by given configparser.ConfigParser() object.
            ioc_temp = IOC(dir_path, verbose)
            if any(config.options(section) for section in config.sections()):
                for section in config.sections():
                    for option in config.options(section):
                        value = config.get(section, option)
                        ioc_temp.set_config(option, value, section)
                print(f'set_ioc: success, set attributes for IOC "{name}" by given settings.')
                ioc_temp.check_consistency(in_container=False)
                if verbose:
                    ioc_temp.show_config()
            else:
                if verbose:
                    print(f'set_ioc: not config given for setting IOC "{name}".')
        else:
            print(f'set_ioc: set attributes failed, IOC "{name}" not exists.')
    else:
        print(f'set_ioc: failed, invalid input args "{name}" for .')


# remove only generated files or remove all, do not accept iterable for input.
def remove_ioc(name, all_remove=False, force_removal=False, verbose=False):
    dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name)
    if os.path.exists(os.path.join(dir_path, CONFIG_FILE)):
        if not force_removal:
            if all_remove:
                print(f'remove_ioc: IOC "{name}" will be removed completely.', end='')
            else:
                print(f'remove_ioc: IOC "{name}" will be removed, but ".ini" file and ".db" files are preserved.',
                      end='')
            ans = input(f'continue?[y|n]:')
            if ans.lower() == 'y' or ans.lower() == 'yes':
                force_removal = True
            else:
                print(f'remove_ioc: failed, remove IOC "{name}" canceled.')
        if force_removal:
            ioc_temp = IOC(dir_path, verbose)
            ioc_temp.remove(all_remove)
            if all_remove:
                print(f'remove_ioc: success, IOC "{name}" removed completely.')
            else:
                print(f'remove_ioc: success, IOC "{name}" removed, but ".ini" file and ".db" files are preserved.')
    else:
        print(f'remove_ioc: failed, IOC "{name}" not found.')


# do nothing, just create an IOC() object by given path to activate its self.__init__() for a name check scheme.
def refresh_ioc(name):
    if isinstance(name, str):
        # may add a name string filter here.
        dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name)
        if os.path.exists(os.path.join(dir_path, CONFIG_FILE)):
            IOC(dir_path)
    elif isinstance(name, Iterable):
        for n in name:
            refresh_ioc(n)


# show all subdirectory IOCs for given path, return the list of all IOCs.
def get_all_ioc(dir_path=None):
    ioc_list = []
    if not dir_path:
        dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP)
    for p in os.listdir(dir_path):
        subdir_path = os.path.join(dir_path, p)
        if os.path.isdir(subdir_path) and CONFIG_FILE in os.listdir(subdir_path):
            ioc_list.append(IOC(subdir_path))
    return ioc_list


# show IOC for specified conditions of specified section, AND logic was implied to each condition.
def get_filtered_ioc(condition: Iterable, section='IOC', show_info=False, verbose=False):
    ioc_list = get_all_ioc()

    index_to_remove = []
    if not condition:
        # default not filter any IOC by options, but filter by sections.
        for i in range(0, len(ioc_list)):
            if not ioc_list[i].conf.has_section(section=section):
                index_to_remove.append(i)
        if verbose:
            print(f'no condition specified, list all IOCs that have section "{section}":')
    elif isinstance(condition, str):
        key, value = condition_parse(condition)
        if key:
            for i in range(0, len(ioc_list)):
                if not ioc_list[i].check_config(key, value, section):
                    index_to_remove.append(i)
            if verbose:
                print(f'results for valid condition "{condition}":')
        else:
            # wrong condition parsed, not return any result.
            index_to_remove = [i for i in range(0, len(ioc_list))]
            if verbose:
                print(f'invalid condition "{condition}" specified.')
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
                    print(f'invalid condition "{c}" specified, skipped.')
        if valid_flag:
            # if there is any valid condition given, not return any result.
            if verbose:
                print(f'results find for valid condition "{valid_condition}":')
        else:
            # if there is no valid condition given, show.
            index_to_remove = [i for i in range(0, len(ioc_list))]
            if verbose:
                print(f'no valid condition specified: "{condition}".')
    else:
        index_to_remove = [i for i in range(0, len(ioc_list))]
        if verbose:
            print(f'no valid condition specified: "{condition}".')

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
        ioc_list[i].check_consistency(in_container=False)


def gen_st_cmd(name, verbose=False, force_executing=False, default_executing=False):
    dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name)
    if os.path.exists(os.path.join(dir_path, CONFIG_FILE)):
        ioc_temp = IOC(dir_path, verbose)
        print(f'gen_st_cmd: start generating st.cmd file for IOC "{name}".')
        ioc_temp.generate_st_cmd(force_executing=force_executing, default_executing=default_executing)
    else:
        print(f'gen_st_cmd: failed, IOC "{name}" not found.')


def add_db_files(name, db_p, verbose=False):
    dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name)
    if os.path.exists(os.path.join(dir_path, CONFIG_FILE)):
        ioc_temp = IOC(dir_path, verbose)
        ioc_temp.get_db_list(db_p)
    else:
        print(f'add_db_files: failed, IOC "{name}" not found.')


def gen_substitution_file(name, verbose=False):
    dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name)
    if os.path.exists(os.path.join(dir_path, CONFIG_FILE)):
        ioc_temp = IOC(dir_path, verbose)
        print(f'gen_substitution_file: start generating {name}.substitutions for IOC "{name}".')
        ioc_temp.generate_substitution_file()
    else:
        print(f'gen_substitution_file: failed, IOC "{name}" not found.')


# generate directory structure for running inside the container.
def repository_to_container(name, gen_path=None, verbose=False):
    dir_path = os.path.join(os.getcwd(), REPOSITORY_TOP, name)
    if os.path.exists(os.path.join(dir_path, CONFIG_FILE)):
        ioc_temp = IOC(dir_path, verbose)

        if not ioc_temp.check_config('status', 'generated'):
            print(f'repository_to_container: failed, attribute "status" get in IOC "{ioc_temp.name}" is not '
                  f'"generated" but "{ioc_temp.get_config("status")}", the directory files may not be prepared.')
            return

        container_name = ioc_temp.get_config('container')
        if not container_name:
            container_name = ioc_temp.name
            if verbose:
                print(f'repository_to_container: attribute "container" not defined in IOC "{ioc_temp.name}", '
                      f'automatically use IOC name as container name.')
        host_name = ioc_temp.get_config('host')
        if not host_name:
            host_name = 'localhost'
            if verbose:
                print(f'repository_to_container: attribute "host" not defined in IOC "{ioc_temp.name}", '
                      f'automatically use "localhost" as host name.')
        if not os.path.isdir(gen_path):
            gen_path = os.getcwd()
            if verbose:
                print(f'repository_to_container: arg "gen_path" invalid or not given, '
                      f'automatically use current work directory as generate path.')
        top_path = os.path.join(gen_path, 'ioc-for-docker', host_name, container_name)
        if dir_copy(ioc_temp.dir_path, top_path, verbose):
            print(f'repository_to_container: success, IOC "{name}" directory created in generate path for docker.')
        else:
            print(f'repository_to_container: failed, for IOC "{name}" you may run this again using "-v" option to see '
                  f'what happened in details.')
    else:
        print(f'repository_to_container: failed, IOC "{name}" not found.')


# Collect files from the container directory to central repository LOG directory.
def container_to_repository(container_path, repository_LOG_path):
    pass


if __name__ == '__main__':
    # argparse
    parser = argparse.ArgumentParser(description='IOC runtime file manager for docker. this script should '
                                                 'be run inside repository directory, where there is a template '
                                                 'folder.')

    subparsers = parser.add_subparsers(
        help='to get subparser help, you may run "./iocManager.py [create|set|exec|list|remove] -h".')

    parser_create = subparsers.add_parser('create', help='create IOC by given settings.')
    parser_create.add_argument('name', type=str, nargs='+', help='IOC name, name list is supported.')
    parser_create.add_argument('-f', '--from-ini-file', type=str,
                               help='settings from specified .ini files, settings created by this '
                                    'option may be override by other options.')
    parser_create.add_argument('-o', '--specify-options', type=str, nargs='+',
                               help='manually specify attribute, format: "key=value". This option may override all '
                                    'other options if conflicts.')
    parser_create.add_argument('-s', '--specify-section', type=str, default='IOC',
                               help='appointing a section for manually specified attribute, default: "IOC".')
    parser_create.add_argument('--putlog', action="store_true", help='add caPutLog.')
    parser_create.add_argument('--ioc-status', action="store_true",
                               help='add devIocStats for IOC monitor.')
    parser_create.add_argument('--os-status', action="store_true",
                               help='add devIocStats for OS monitor.')
    parser_create.add_argument('--autosave', action="store_true", help='add autosave.')
    parser_create.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_create.set_defaults(func='parse_create')

    parser_set = subparsers.add_parser('set', help='set attributes for IOC.')
    parser_set.add_argument('name', type=str, nargs='+', help='IOC name, name list is supported.')
    parser_set.add_argument('-f', '--from-ini-file', type=str,
                            help='settings from specified .ini files, settings set by this '
                                 'option may be override by other options.')
    parser_set.add_argument('-o', '--specify-options', type=str, nargs='+',
                            help='manually specify attribute, format: "key=value". This option may override all '
                                 'other options if conflicts.')
    parser_set.add_argument('-s', '--specify-section', type=str, default='IOC',
                            help='appointing a section for manually specified attribute, default: "IOC".')
    parser_set.add_argument('--putlog', action="store_true", help='set caPutLog.')
    parser_set.add_argument('--ioc-status', action="store_true",
                            help='set devIocStats for IOC monitor.')
    parser_set.add_argument('--os-status', action="store_true",
                            help='set devIocStats for OS monitor.')
    parser_set.add_argument('--autosave', action="store_true", help='set autosave.')
    parser_set.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_set.set_defaults(func='parse_set')

    parser_execute = subparsers.add_parser('exec', help='execute functions for IOC.')
    parser_execute.add_argument('name', type=str, nargs='+', help='IOC name, name list is supported.')
    parser_execute.add_argument('-g', '--generate-st-cmd', action="store_true", help='generate st.cmd file.')
    parser_execute.add_argument('--force-silent', action="store_true",
                                help='force generating st.cmd file and do not ask.')
    parser_execute.add_argument('--default-install', action="store_true",
                                help='force generating st.cmd file using default.')
    parser_execute.add_argument('-o', '--to-docker', action="store_true", help='copy generated IOC directory files '
                                                                               'out to a path for docker deployment.')
    parser_execute.add_argument('--generate-path', type=str, default='',
                                help='appointing a generate path where all files go into, default: current work path.')
    parser_execute.add_argument('-d', '--add-db-files', action="store_true",
                                help='add db files from given directory and update ioc.ini file.')
    parser_execute.add_argument('--db-path', type=str, default='',
                                help='appointing a path where all db files exist, default: use "*/startup/db/".')
    parser_execute.add_argument('-s', '--generate-substitution-file', action="store_true",
                                help='generate .substitution file for st.cmd to load db files.')
    parser_execute.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_execute.set_defaults(func='parser_execute')

    parser_list = subparsers.add_parser('list', help='get existing IOC by given conditions.')
    parser_list.add_argument('condition', type=str, nargs='*',
                             help='conditions to filter IOC, list all IOC if no input provided.')
    parser_list.add_argument('-s', '--specify-section', type=str, default='IOC',
                             help='appointing a section for filter, default: "IOC".')
    parser_list.add_argument('-v', '--verbose', action="store_true", help='show details.')
    parser_list.add_argument('-i', '--show-info', action="store_true", help='show details of IOC.')
    parser_list.set_defaults(func='parse_list')

    parser_remove = subparsers.add_parser('remove', help='remove IOC.')
    parser_remove.add_argument('name', type=str, nargs='+', help='IOC name, name list is supported.')
    parser_remove.add_argument('-r', '--remove-all', action="store_true",
                               help='remove entire IOC, this will remove all files of an IOC.')
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
        if args.from_ini_file:
            if conf_temp.read(args.from_ini_file):
                if args.verbose:
                    print(f'read .ini file "{args.from_ini_file}".')
            else:
                if args.verbose:
                    print('invalid .ini file "{args.from_ini_file}" specified, skipped.')
        #
        module_installed = ''
        if args.autosave:
            module_installed += 'autosave, '
        if args.putlog:
            module_installed += 'caputlog, '
        if args.ioc_status:
            module_installed += 'ioc-status, '
        if args.os_status:
            module_installed += 'os-status, '
        module_installed = module_installed.rstrip(', ')
        if module_installed:
            if not conf_temp.has_section('IOC'):
                conf_temp.add_section('IOC')
            conf_temp.set('IOC', 'module', module_installed)
            if args.verbose:
                print(f'set "module : {module_installed}" according to specified options for section "IOC".')
        #
        if args.specify_options:
            if not conf_temp.has_section(args.specify_section):
                conf_temp.add_section(args.specify_section)
            for item in args.specify_options:
                k, v = condition_parse(item, 1)
                if k:
                    conf_temp.set(args.specify_section, k, v)
                    if args.verbose:
                        print(f'set "{k}: {v}" for section "{args.specify_section}".')
                else:
                    if args.verbose:
                        print(f'wrong option "{item}" for section "{args.specify_section}", skipped.')
        #
        if args.func == 'parse_create':
            # ./iocManager.py create
            create_ioc(args.name, args.verbose, conf_temp)
        else:
            # ./iocManager.py set
            for item in args.name:
                set_ioc(item, args.verbose, config=conf_temp)
    if args.func == 'parse_list':
        get_filtered_ioc(args.condition, section=args.specify_section, show_info=args.show_info, verbose=args.verbose)
    if args.func == 'parse_remove':
        for item in args.name:
            remove_ioc(item, all_remove=args.remove_all, force_removal=args.force, verbose=args.verbose)
    if args.func == 'parser_execute':
        for item in args.name:
            if args.add_db_files:
                add_db_files(item, args.db_path, verbose=args.verbose)
            if args.generate_substitution_file:
                gen_substitution_file(item, verbose=args.verbose)
            if args.generate_st_cmd:
                gen_st_cmd(item, verbose=args.verbose, force_executing=args.force_silent,
                           default_executing=args.default_install)
            if args.to_docker:
                repository_to_container(item, args.generate_path, args.verbose)
