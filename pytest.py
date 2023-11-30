#!/usr/bin/python3
import configparser
import os
import unittest

import IocManager as IM


class TestIOCCLassFunctions(unittest.TestCase):

    def setUp(self):
        self.top_dir = os.getcwd()
        self.test0_dir = os.path.join(self.top_dir, IM.REPOSITORY_TOP, 'test0')
        self.test1_dir = os.path.join(self.top_dir, IM.REPOSITORY_TOP, 'test1')
        self.test2_dir = os.path.join(self.top_dir, IM.REPOSITORY_TOP, 'test2')
        self.verbose = True
        print(f"\nRunning test: {self._testMethodName}")
        print('-' * 73)

    def tearDown(self):
        pass

    def test_a_default_IOC_init(self):
        self.i = IM.IOC(verbose=self.verbose)
        self.i.show_config()
        self.i.remove(True)

    def test_b_single_IOC_init_and_partial_remove(self):
        IM.try_makedirs(self.test0_dir)
        self.i = IM.IOC(self.test0_dir, verbose=self.verbose)
        # create .ini
        self.assertTrue(os.path.exists(self.i.config_file_path))
        # create startup/ioc/
        self.assertTrue(os.path.exists(self.i.dir_path))
        # create startup/ioc/db/
        self.assertTrue(os.path.exists(self.i.db_path))
        # create startup/ioc/iocBoot/
        self.assertTrue(os.path.exists(self.i.boot_path))
        # create log/ioc/
        self.assertTrue(os.path.exists(self.i.log_path))
        # create settings/ioc/
        self.assertTrue(os.path.exists(self.i.settings_path))

        self.i.remove()
        # delete startup/ioc/iocBoot/
        self.assertFalse(os.path.exists(self.i.boot_path))
        # delete log/ioc/
        self.assertFalse(os.path.exists(self.i.log_path))
        # delete settings/ioc/
        self.assertFalse(os.path.exists(self.i.settings_path))
        # partial removal not delete follows.
        self.assertTrue(os.path.exists(os.path.join(self.i.config_file_path)))
        self.assertTrue(os.path.exists(self.i.dir_path))
        self.assertTrue(os.path.exists(self.i.db_path))

        self.i.remove(all_remove=True)

    def test_c_single_IOC_init_and_total_remove(self):
        IM.try_makedirs(self.test0_dir)
        self.i = IM.IOC(self.test0_dir, verbose=self.verbose)
        # create .ini
        self.assertTrue(os.path.exists(self.i.config_file_path))
        # create startup/ioc/
        self.assertTrue(os.path.exists(self.i.dir_path))
        # create startup/ioc/db/
        self.assertTrue(os.path.exists(self.i.db_path))
        # create startup/ioc/iocBoot/
        self.assertTrue(os.path.exists(self.i.boot_path))
        # create log/ioc/
        self.assertTrue(os.path.exists(self.i.log_path))
        # create settings/ioc/
        self.assertTrue(os.path.exists(self.i.settings_path))

        self.i.remove(all_remove=True)
        # delete startup/ioc/iocBoot/
        self.assertFalse(os.path.exists(self.i.boot_path))
        # delete log/ioc/
        self.assertFalse(os.path.exists(self.i.log_path))
        # delete settings/ioc/
        self.assertFalse(os.path.exists(self.i.settings_path))
        # total removal also delete follows.
        self.assertFalse(os.path.exists(self.i.config_file_path))
        self.assertFalse(os.path.exists(self.i.db_path))
        # total removal not delete follows.
        self.assertFalse(os.path.exists(self.i.dir_path))

    def test_d_multiple_IOC_init_and_partial_remove(self):
        IM.try_makedirs(self.test0_dir)
        IM.try_makedirs(self.test1_dir)
        self.i0 = IM.IOC(self.test0_dir, verbose=self.verbose)
        self.i1 = IM.IOC(self.test1_dir, verbose=self.verbose)

        self.i0.remove()
        self.assertTrue(os.path.exists(self.i0.config_file_path))
        self.assertTrue(os.path.exists(self.i0.db_path))
        self.assertTrue(os.path.exists(self.i0.dir_path))
        self.assertFalse(os.path.exists(self.i0.boot_path))
        self.assertFalse(os.path.exists(self.i0.log_path))
        self.assertFalse(os.path.exists(self.i0.settings_path))
        # i1 not influenced.
        self.assertTrue(os.path.exists(self.i1.config_file_path))
        self.assertTrue(os.path.exists(self.i1.db_path))
        self.assertTrue(os.path.exists(self.i1.dir_path))
        self.assertTrue(os.path.exists(self.i1.boot_path))
        self.assertTrue(os.path.exists(self.i1.log_path))
        self.assertTrue(os.path.exists(self.i1.settings_path))

        self.i0.remove(True)
        self.i1.remove(True)

    def test_e_multiple_IOC_init_and_total_remove(self):
        IM.try_makedirs(self.test0_dir)
        IM.try_makedirs(self.test1_dir)
        self.i0 = IM.IOC(self.test0_dir, verbose=self.verbose)
        self.i1 = IM.IOC(self.test1_dir, verbose=self.verbose)

        self.i0.remove(True)
        self.assertFalse(os.path.exists(self.i0.config_file_path))
        self.assertFalse(os.path.exists(self.i0.db_path))
        self.assertFalse(os.path.exists(self.i0.dir_path))
        self.assertFalse(os.path.exists(self.i0.boot_path))
        self.assertFalse(os.path.exists(self.i0.log_path))
        self.assertFalse(os.path.exists(self.i0.settings_path))
        # i1 not influenced.
        self.assertTrue(os.path.exists(self.i1.config_file_path))
        self.assertTrue(os.path.exists(self.i1.db_path))
        self.assertTrue(os.path.exists(self.i1.dir_path))
        self.assertTrue(os.path.exists(self.i1.boot_path))
        self.assertTrue(os.path.exists(self.i1.log_path))
        self.assertTrue(os.path.exists(self.i1.settings_path))

        self.i0.remove(True)
        self.i1.remove(True)

    def test_f_initialize_an_existed_IOC_and_change_options_sections(self):
        IM.try_makedirs(self.test0_dir)
        self.i0 = IM.IOC(self.test0_dir, verbose=self.verbose)
        self.i1 = IM.IOC(self.test0_dir, verbose=self.verbose)
        self.i0.set_config('bin', 'asdasd')
        # self.i0.show_config()
        # self.i1.show_config()
        self.i1.read_config()  # refresh conf attribute.
        # self.i1.show_config()
        self.assertTrue(self.i1.check_config('bin', 'asdasd'))

        self.i0.set_config('aaaa', 'bbbb', 'acc')
        self.i1.read_config()  # refresh conf attribute.
        self.assertTrue(self.i1.check_config('aaaa', 'bbbb', 'acc'))
        self.assertFalse(self.i1.check_config('aaaa', 'bbbb'))
        self.i0.remove(True)

    def test_g_generated_st_cmd(self):
        IM.try_makedirs(self.test0_dir)
        self.i = IM.IOC(self.test0_dir, verbose=self.verbose)
        self.assertEqual(self.i.get_config('status').lower(), 'created')
        self.i.set_config('bin', 'ST-IOC')
        self.i.set_config('modules', 'caputlog, autosave, ioc-status, os-status')
        self.i.generate_st_cmd()
        self.assertEqual(self.i.get_config('status').lower(), 'generated')
        print('.' * 73)
        with open(os.path.join(self.i.boot_path, 'st.cmd'), 'r') as file:
            file_content = file.read()
            print(file_content)
        self.i.remove(all_remove=True)

    def test_h_generated_st_cmd_by_wrong_setting(self):
        IM.try_makedirs(self.test0_dir)
        self.i = IM.IOC(self.test0_dir, verbose=self.verbose)
        self.assertEqual(self.i.get_config('status').lower(), 'created')
        self.i.set_config('bin', 'ST-IOC')
        self.i.set_config('modules', 'cap')
        self.i.generate_st_cmd()
        print('.' * 73)
        with open(os.path.join(self.i.boot_path, 'st.cmd'), 'r') as file:
            file_content = file.read()
            print(file_content)
        self.i.remove(True)


class TestIOCManagerFunctions(unittest.TestCase):
    def setUp(self):
        self.top_dir = os.getcwd()
        self.verbose = False
        print(f"\nRunning test: {self._testMethodName}")
        print('-' * 73)

    def assert_ioc_exits_or_not(self, ioc_name, assert_not=False, completely=False):
        if assert_not:
            if completely:
                self.assertFalse(os.path.exists(os.path.join(self.top_dir, IM.REPOSITORY_TOP, ioc_name, 'startup')))
                self.assertFalse(os.path.exists(os.path.join(self.top_dir, IM.REPOSITORY_TOP, ioc_name, 'log')))
                self.assertFalse(os.path.exists(os.path.join(self.top_dir, IM.REPOSITORY_TOP, ioc_name, 'settings')))
            else:
                self.assertTrue(os.path.exists(os.path.join(self.top_dir, IM.REPOSITORY_TOP, ioc_name, 'startup')))
                self.assertTrue(os.path.exists(os.path.join(self.top_dir, IM.REPOSITORY_TOP, ioc_name, IM.CONFIG_FILE)))
                self.assertTrue(
                    os.path.exists(os.path.join(self.top_dir, IM.REPOSITORY_TOP, ioc_name, 'startup', 'db')))
                self.assertFalse(
                    os.path.exists(os.path.join(self.top_dir, IM.REPOSITORY_TOP, ioc_name, 'startup', 'iocBoot')))
                self.assertFalse(os.path.exists(os.path.join(self.top_dir, IM.REPOSITORY_TOP, ioc_name, 'log')))
                self.assertFalse(os.path.exists(os.path.join(self.top_dir, IM.REPOSITORY_TOP, ioc_name, 'settings')))
        else:
            self.assertTrue(os.path.exists(os.path.join(self.top_dir, IM.REPOSITORY_TOP, ioc_name, 'startup')))
            self.assertTrue(os.path.exists(os.path.join(self.top_dir, IM.REPOSITORY_TOP, ioc_name, IM.CONFIG_FILE)))
            self.assertTrue(os.path.exists(os.path.join(self.top_dir, IM.REPOSITORY_TOP, ioc_name, 'startup', 'db')))
            self.assertTrue(
                os.path.exists(os.path.join(self.top_dir, IM.REPOSITORY_TOP, ioc_name, 'startup', 'iocBoot')))
            self.assertTrue(os.path.exists(os.path.join(self.top_dir, IM.REPOSITORY_TOP, ioc_name, 'log')))
            self.assertTrue(os.path.exists(os.path.join(self.top_dir, IM.REPOSITORY_TOP, ioc_name, 'settings')))

    def test_a_create_ioc_by_given_settings(self):
        conf = configparser.ConfigParser()
        conf['IOC'] = {
            'aaa': 'aaaa',
            'bbb': 'bbbb',
            'name': 'nnnn',
        }
        conf['asd'] = {
            'ccc': 'cccc',
        }
        IM.create_ioc('abc', verbose=self.verbose, config=conf)
        dir_path = os.path.join(self.top_dir, IM.REPOSITORY_TOP, 'abc')
        ioc = IM.IOC(dir_path, verbose=self.verbose)
        ioc.show_config()
        for section in conf.sections():
            for option in conf.options(section):
                if option == 'name' and section == 'IOC':
                    self.assertNotEqual(ioc.get_config(option, section), conf.get(section, option))
                else:
                    self.assertEqual(ioc.get_config(option, section), conf.get(section, option))
        IM.remove_ioc('abc', all_remove=True, force_removal=True)

    def test_b_create_one_or_multiple_ioc_and_remove(self):
        ilist = ['abc', 'def', 'ghi']
        IM.create_ioc(ilist)
        for item in ilist:
            self.assert_ioc_exits_or_not(item)
            IM.remove_ioc(item, force_removal=True)
            self.assert_ioc_exits_or_not(item, assert_not=True)
            IM.remove_ioc(item, all_remove=True, force_removal=True)
        IM.create_ioc(ilist)
        for item in ilist:
            self.assert_ioc_exits_or_not(item)
            IM.remove_ioc(item, all_remove=True, force_removal=True)
            self.assert_ioc_exits_or_not(item, assert_not=True, completely=True)

    def test_c_create_an_exist_ioc(self):
        IM.create_ioc('abc')
        IM.create_ioc('abc')
        IM.remove_ioc('abc', force_removal=True)
        IM.create_ioc('abc')
        IM.remove_ioc('abc', all_remove=True, force_removal=True)
        IM.create_ioc('abc')
        IM.remove_ioc('abc', all_remove=True, force_removal=True)

    def test_d_set_ioc_and_generate_st_cmd(self):
        conf = configparser.ConfigParser()
        conf['IOC'] = {
            'aaa': 'aaaa',
            'bbb': 'bbbb',
            'modules': 'caputlog',
        }
        conf['asd'] = {
            'ccc': 'cccc',
        }
        IM.create_ioc('abc', verbose=self.verbose, config=conf)
        IM.create_ioc('def', verbose=self.verbose)
        # IM.set_ioc('def', verbose=self.verbose, config=conf, gen_flag=True)
        IM.get_filtered_ioc('aaa=aaaa', True)
        IM.set_ioc('def', verbose=self.verbose, config=conf)
        IM.get_filtered_ioc('name=def', True)
        IM.remove_ioc('abc', True, force_removal=True)
        IM.remove_ioc('def', True, force_removal=True)
        pass

    def test_e_condition_parse(self):
        res1, res2 = IM.condition_parse(' a = b ')
        self.assertEqual(res1, 'a')
        self.assertEqual(res2, 'b')
        res1, res2 = IM.condition_parse('  = basdsd1 ')
        self.assertEqual(res1, None)
        self.assertEqual(res2, None)
        res1, res2 = IM.condition_parse(' sadsadad =  ')
        self.assertEqual(res1, 'sadsadad')
        self.assertEqual(res2, '')
        res1, res2 = IM.condition_parse(' sadsadad = 1 ')
        self.assertEqual(res1, 'sadsadad')
        self.assertEqual(res2, '1')
        res1, res2 = IM.condition_parse(' sadsadad == 1 ')
        self.assertEqual(res1, None)
        self.assertEqual(res2, None)

    def test_f_multiple_ioc_filter(self):
        # self.verbose =True
        conf = configparser.ConfigParser()
        conf['IOC'] = {
            'aaa': 'aaaa',
            'bbb': 'bbbb',
            'modules': 'caputlog',
        }
        conf['asd'] = {
            'ccc': 'cccc',
        }
        IM.create_ioc('abc', verbose=self.verbose, config=conf)
        IM.create_ioc('def', verbose=self.verbose)
        IM.create_ioc('ghi', verbose=self.verbose, config=conf)
        IM.get_filtered_ioc(['modules=caputlog', 'name=ghi'])
        IM.get_filtered_ioc(['modules=cap'])
        IM.get_filtered_ioc(['container='])
        IM.get_filtered_ioc(['contassssiner='])
        IM.get_filtered_ioc(['moSdules=caputlog', 'name=ghi'], show_info=True)
        IM.get_filtered_ioc(['modules=caputlog', 'name=gh2i'])
        IM.get_filtered_ioc(['=caputlog', 'name=gh2i'])
        IM.get_filtered_ioc(['=caputlog', 'name='])

        IM.remove_ioc('abc', True, force_removal=True)
        IM.remove_ioc('def', True, force_removal=True)
        IM.remove_ioc('ghi', True, force_removal=True)
