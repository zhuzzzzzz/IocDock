#!/bin/bash

script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

# 为 EPICS base 定义要构建的版本数组
# 格式 "base_version;release_version"
versions_to_build_for_base=("7.0.8.1;1.0.0" )

# 为 ioc-exec 定义要构建的版本数组
# 格式 "base_version;base_release_version;release_version;[moduleA [moduleB ...]]"
versions_to_build_for_ioc_exec=(
    "7.0.8.1;1.0.0;1.0.0;seq autosave caPutLog iocStats" 
    "7.0.8.1;1.0.0;1.0.1;seq asyn autosave caPutLog iocStats StreamDevice modbus" 
    "7.0.8.1;1.0.0;1.0.2;seq asyn autosave caPutLog iocStats s7nodave" 
    "7.0.8.1;1.0.0;1.0.3;seq autosave caPutLog iocStats BACnet" 
    "7.0.8.1;1.0.0;1.0.A;seq asyn autosave caPutLog iocStats StreamDevice modbus s7nodave BACnet" 
)

print_log=""

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --print-log)
            print_log_option="true"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--print-log]"
            exit 1
            ;;
    esac
done

# 输出配置信息
echo "=============================================="
echo "Configuration Summary:"
echo "----------------------------------------------"
echo "Versions to Build and Release for EPICS Base:"
for version in "${versions_to_build_for_base[@]}"; do
    IFS=';' read -r base_ver base_rel <<< "$version"
    echo "  - Base: $base_ver, Release: $base_rel"
done
echo ""
echo "----------------------------------------------"
echo "Versions to Build and Release for ioc-exec:"
for version in "${versions_to_build_for_ioc_exec[@]}"; do
    IFS=';' read -r base_ver base_rel rel modules <<< "$version"
    echo "  - Base: $base_ver, Base Release: $base_rel, Release: $rel, Modules: $modules"
done
echo "=============================================="

# 询问用户是否继续
read -p "Do you want to continue with the build process? (y/N): " continue_choice
if [[ ! $continue_choice =~ ^[Yy]$ ]]; then
    echo "Build process cancelled."
    exit 1
fi

echo
echo "Start building and releasing images for EPICS base..."
echo
set -ex
cd $script_dir/base
{ set +x; } 2>/dev/null
# 遍历版本数组进行构建
for arg_list in "${versions_to_build_for_base[@]}"; do
    # 分割字符串获取 base 版本和 release 版本
    IFS=';' read -r base_version base_release_version <<< "$arg_list"
    set -x
    ./build-and-push.sh --base=$base_version --release=$base_release_version ${print_log_option:+--print-log}
    { set +x; } 2>/dev/null
    echo
done

echo
echo "Start building and releasing images for ioc-exec..."
echo
set -x
cd $script_dir/ioc-exec
{ set +x; } 2>/dev/null
# 遍历版本数组进行构建
for arg_list in "${versions_to_build_for_ioc_exec[@]}"; do
    # 分割字符串获取 base 、base_release 、release 、模块列表
    IFS=';' read -r base_version base_release_version release_version modules <<< "$arg_list"
    set -x
    ./build-and-push.sh --base-version=$base_version \
        --base-release=$base_release_version \
        --release=$release_version \
        "--modules=$modules" \
        ${print_log_option:+--print-log}
    { set +x; } 2>/dev/null
    echo
done