#!/bin/bash

# Script for testing a specific EPICS image

if [ $# -lt 2 ]; then
    echo "Usage: $0 <image_type> <image_tag>"
    echo "Example: $0 base 1.0.0"
    echo "Example: $0 ioc-exec 1.0.0"
    exit 1
fi

image_type=$1
image_tag=$2

echo "==================================="
echo "Testing $image_type:$image_tag image"
echo "==================================="

# 初始化计数器
total_tests=0
passed_tests=0
failed_tests=0

# 函数：记录测试结果
record_test() {
    local result=$1
    local description=$2
    
    ((total_tests++))
    if [ "$result" = "PASS" ]; then
        echo "✓ $description"
        ((passed_tests++))
    else
        echo "✗ $description"
        ((failed_tests++))
    fi
}

# Check if image exists
if ! docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^$image_type:$image_tag$"; then
    echo "Error: $image_type:$image_tag image not found!"
    exit 1
else
    echo "✓ $image_type:$image_tag image found"
fi

# Run tests for the image
container_id=$(docker create $image_type:$image_tag sleep infinity)
docker start $container_id > /dev/null

if [ "$image_type" = "base" ]; then
    # Tests specific to base image
    echo "Running tests for base image..."
    
    # Check environment variables
    echo "Checking environment variables..."
    if docker exec $container_id env | grep -q "EPICS_BASE"; then
        record_test PASS "EPICS_BASE environment variable is set. EPICS_BASE=$(docker exec $container_id printenv EPICS_BASE)"
    else
        record_test FAIL "EPICS_BASE environment variable not found"
    fi

    if docker exec $container_id env | grep -q "EPICS_HOST_ARCH"; then
        record_test PASS "EPICS_HOST_ARCH environment variable is set. EPICS_HOST_ARCH=$(docker exec $container_id printenv EPICS_HOST_ARCH)"
    else
        record_test FAIL "EPICS_HOST_ARCH environment variable not found"
    fi

    # Check if softIoc command works
    echo "Checking softIoc command..."
    if docker exec $container_id softIoc -h > /dev/null 2>&1; then
        record_test PASS "softIoc command is available"
    else
        record_test FAIL "softIoc command not found"
    fi

    # Check if makeBaseApp.pl command works
    echo "Checking makeBaseApp.pl command..."
    if docker exec $container_id makeBaseApp.pl -h > /dev/null 2>&1; then
        record_test PASS "makeBaseApp.pl command is available"
    else
        record_test FAIL "makeBaseApp.pl command not found"
    fi

elif [ "$image_type" = "ioc-exec" ]; then
    # Tests specific to ioc-exec image
    echo "Running tests for ioc-exec image..."

    # Install build tools and libraries
    echo "Checking for Installing build tools and libraries..."
    if docker exec $container_id apt update > /dev/null 2>&1; then
        if docker exec $container_id apt install -y build-essential libreadline-dev python3 zip > /dev/null 2>&1; then
            record_test PASS "Build tools and libraries installed successfully"
        else
            record_test FAIL "Failed to install tools and libraries"
        fi
    else
        record_test FAIL "Failed to update package list"
    fi

    # Check IOC build via test-for-ioc-generator.sh
    echo "Checking IOC bulid via test-for-ioc-generator.sh..."
    if docker exec $container_id /opt/EPICS/IOC/ioc-tools/test-for-ioc-generator.sh > /dev/null 2>&1; then
        record_test PASS "Build IOC project successfully"
    else
        record_test FAIL "Failed to build IOC project"
    fi

else
    echo "Unknown image type: $image_type"
    exit 1
fi

# Stop and remove container
docker stop $container_id > /dev/null
docker rm $container_id > /dev/null

# 输出测试总结
echo
echo "==================================="
echo "Test Summary for $image_type:$image_tag:"
echo "Total tests: $total_tests"
echo "Passed: $passed_tests"
echo "Failed: $failed_tests"
echo "==================================="

# 根据测试结果设置退出码
if [ $failed_tests -gt 0 ]; then
    echo "Some tests failed for $image_type:$image_tag. Exiting with status 1."
    exit 1
else
    echo "All tests passed for $image_type:$image_tag. Exiting successfully."
    exit 0
fi