#!/bin/bash

script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

PRINT='-p' # '' or '-p'
VERBOSE='' # '' or '-v'

if [ $# -gt 0 ]; then
    for arg in "$@"; do
        if [ "$arg" == "-v" ]; then
            VERBOSE='-v'
        fi
    done
fi

echo_paragraph(){
echo 
echo
echo $1
echo '<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<'
echo
echo
}

echo_segment(){
echo '>>>>>>>>>>>>>>>>>'
echo_line $*
}

echo_line(){
echo 
echo $*
echo "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
}


#######
# test for ./IocManager.py create
echo_paragraph 'test for "./IocManager.py create"'

string="./IocManager.py create test $PRINT $VERBOSE"
echo_segment "$string"
eval $string

string="./IocManager.py create test1 $PRINT $VERBOSE --caputlog --status-ioc --status-os --autosave"
echo_line "$string"
eval $string

string="./IocManager.py create test2 $PRINT $VERBOSE --add-asyn"
echo_line "$string"
eval $string

string="./IocManager.py create test3 $PRINT $VERBOSE --add-asyn --port-type serial"
echo_line "$string"
eval $string

string="./IocManager.py create test4 $PRINT $VERBOSE --add-stream"
echo_line "$string"
eval $string

string="./IocManager.py create test5 $PRINT $VERBOSE --add-stream --port-type serial"
echo_line "$string"
eval $string

string="./IocManager.py create test6 $PRINT $VERBOSE --add-raw"
echo_line "$string"
eval $string

string="./IocManager.py create test7 $PRINT $VERBOSE -f './imtools/template/test/test.ini'"
echo_line "$string"
eval $string

string="./IocManager.py create test8 $PRINT $VERBOSE -f './imtools/template/test/test.ini' --caputlog"
echo_line "$string"
eval $string

string="./IocManager.py create test9 $PRINT $VERBOSE -f './imtools/template/test/test.ini' -o 'module=abc'"
echo_line "$string"
eval $string

string="./IocManager.py create test10 $PRINT $VERBOSE -o ' a = b' 'c = d' -s test"
echo_line "$string"
eval $string

string="./IocManager.py remove test test1 test2 test3 test4 test5 test6 test7 test8 test9 test10 -rf $VERBOSE"
echo_line "$string"
eval $string


#######
# test for ./IocManager.py set
echo_paragraph 'test for "./IocManager.py set"'

string="./IocManager.py create test $PRINT $VERBOSE"
echo_segment "$string"
eval $string

string="./IocManager.py set test $PRINT $VERBOSE --caputlog --status-ioc --status-os --autosave"
echo_line "$string"
eval $string

string="./IocManager.py set test $PRINT $VERBOSE --add-asyn"
echo_line "$string"
eval $string

string="./IocManager.py set test $PRINT $VERBOSE --add-asyn --port-type serial"
echo_line "$string"
eval $string

string="./IocManager.py set test $PRINT $VERBOSE --add-stream"
echo_line "$string"
eval $string

string="./IocManager.py set test $PRINT $VERBOSE --add-stream --port-type serial"
echo_line "$string"
eval $string

string="./IocManager.py set test $PRINT $VERBOSE -f './imtools/template/test/test.ini'"
echo_line "$string"
eval $string

string="./IocManager.py set test $PRINT $VERBOSE -f './imtools/template/test/test.ini' --caputlog"
echo_line "$string"
eval $string

string="./IocManager.py set test $PRINT $VERBOSE -f './imtools/template/test/test.ini' -o 'module=abc'"
echo_line "$string"
eval $string

string="./IocManager.py set test $PRINT $VERBOSE -o ' a = b' 'c = d' -s test"
echo_line "$string"
eval $string

string="./IocManager.py remove test -rf $VERBOSE"
echo_line "$string"
eval $string

#######
# test for ./IocManager.py exec
echo_paragraph 'test for "./IocManager.py exec"'

string="./IocManager.py create test $PRINT $VERBOSE"
echo_segment "$string"
eval $string

string="./IocManager.py exec test $VERBOSE -s "
echo_line "$string"
eval $string

string="./IocManager.py set test $PRINT $VERBOSE -f './imtools/template/test/test.ini'"
echo_line "$string"
eval $string

string="./IocManager.py exec test $VERBOSE -g"
echo_line "$string"
eval $string

string="./IocManager.py exec test $VERBOSE -s --src-path ./imtools/template/test"
echo_line "$string"
eval $string

string="./IocManager.py exec test $VERBOSE -g"
echo_line "$string"
eval $string
echo
echo tree ./ioc-repository/test
tree ./ioc-repository/test

string="./IocManager.py exec test $VERBOSE -c"
echo_line "$string"
eval $string

string="./IocManager.py exec test $VERBOSE -o"
echo_line "$string"
eval $string
echo
echo tree ioc-for-docker
tree ./ioc-for-docker

mkdir tt
string="./IocManager.py exec test $VERBOSE -o --mount-path ./tt"
echo_line "$string"
eval $string
echo
echo tree ./tt
tree ./tt
rm -rf ./tt/

string="./IocManager.py remove test -rf $VERBOSE"
echo_line "$string"
eval $string


#######
# test for ./IocManager.py list
echo_paragraph 'test for "./IocManager.py list"'

string="./IocManager.py create test1 $VERBOSE --caputlog --status-ioc --status-os --autosave"
eval $string

string="./IocManager.py create test2  $VERBOSE --add-asyn"
eval $string

string="./IocManager.py create test3 $VERBOSE --add-asyn --port-type serial"
eval $string

string="./IocManager.py create test4 $VERBOSE --add-stream"
eval $string

string="./IocManager.py create test5 $VERBOSE --add-stream --port-type serial"
eval $string

string="./IocManager.py create test6 $VERBOSE --add-raw"
eval $string

string="./IocManager.py create test7 $VERBOSE -f './imtools/template/test/test.ini'"
eval $string

string="./IocManager.py create test8 $VERBOSE -f './imtools/template/test/test.ini' --caputlog"
eval $string

string="./IocManager.py create test9 $VERBOSE -f './imtools/template/test/test.ini' -o 'module=abc'"
eval $string

string="./IocManager.py create test10 $VERBOSE -o ' a = b' 'c = d' -s test"
eval $string

string="./IocManager.py list $VERBOSE"
echo_line "$string"
eval $string

string="./IocManager.py list 'a = b' -s test $VERBOSE"
echo_line "$string"
eval $string

string="./IocManager.py list 'a = c' -s test $VERBOSE"
echo_line "$string"
eval $string

string="./IocManager.py list 'module = caputlog' $VERBOSE"
echo_line "$string"
eval $string

string="./IocManager.py list 'module = cap' $VERBOSE"
echo_line "$string"
eval $string

string="./IocManager.py list 'module = cap' $VERBOSE | ./IocManager.py list 'module = aut' $VERBOSE"
echo_line "$string"
eval $string

string="./IocManager.py list -s asyn $VERBOSE"
echo_line "$string"
eval $string

string="./IocManager.py remove test test1 test2 test3 test4 test5 test6 test7 test8 test9 test10 -rf $VERBOSE"
echo_line "$string"
eval $string


#######
# test finished
echo_paragraph 'test finished'
