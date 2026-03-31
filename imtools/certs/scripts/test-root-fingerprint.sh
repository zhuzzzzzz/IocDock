#!/bin/bash

# =============================================================================
# 证书管理工具 - 根证书指纹验证测试
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERTS_DIR="$SCRIPT_DIR/../certs"
TEST_PASSED=0
TEST_FAILED=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_test() {
    echo -e "${YELLOW}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TEST_PASSED++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TEST_FAILED++))
}

cleanup() {
    log_test "清理测试环境..."
    rm -rf "$CERTS_DIR/test_root"
    rm -rf "$CERTS_DIR/root/Test_CA"
    rm -rf "$CERTS_DIR/intermediate/test_service"
    rm -f "$CERTS_DIR/root/.root_fingerprint"
}

# -----------------------------------------------------------------------------
# 测试 1: 生成根证书并验证指纹保存
# -----------------------------------------------------------------------------
test_root_cert_fingerprint_saved() {
    log_test "测试 1: 生成根证书并验证指纹文件创建"
    
    cd "$SCRIPT_DIR"
    ./make-certs.sh --root \
        --common-name "Test CA" \
        --output-dir "$CERTS_DIR" \
        --days 365 \
        --force
    
    local fingerprint_file="$CERTS_DIR/root/.root_fingerprint"
    if [[ -f "$fingerprint_file" ]]; then
        log_pass "根证书指纹文件已创建"
        
        # 验证指纹文件格式
        local fingerprint=$(cat "$fingerprint_file")
        if [[ ${#fingerprint} -gt 50 ]]; then
            log_pass "指纹格式正确（长度：${#fingerprint}）"
        else
            log_fail "指纹格式异常（长度：${#fingerprint}）"
        fi
    else
        log_fail "根证书指纹文件未创建"
    fi
}

# -----------------------------------------------------------------------------
# 测试 2: 生成中间证书时验证根证书指纹
# -----------------------------------------------------------------------------
test_intermediate_cert_with_fingerprint() {
    log_test "测试 2: 生成中间证书时验证根证书指纹"
    
    cd "$SCRIPT_DIR"
    ./make-certs.sh --intermediate test_service \
        --common-name "test.service.local" \
        --root-cert "$CERTS_DIR/root/Test_CA.crt" \
        --root-key "$CERTS_DIR/root/Test_CA.key" \
        --output-dir "$CERTS_DIR" \
        --days 180 \
        --force
    
    if [[ -f "$CERTS_DIR/intermediate/test_service/test.service.local.crt" ]]; then
        log_pass "中间证书生成成功"
    else
        log_fail "中间证书生成失败"
    fi
}

# -----------------------------------------------------------------------------
# 测试 3: 根证书被替换后检测不匹配
# -----------------------------------------------------------------------------
test_root_cert_replacement_detected() {
    log_test "测试 3: 检测根证书被替换"
    
    # 备份原有根证书
    cp "$CERTS_DIR/root/Test_CA.crt" "$CERTS_DIR/root/Test_CA.crt.bak"
    cp "$CERTS_DIR/root/Test_CA.key" "$CERTS_DIR/root/Test_CA.key.bak"
    
    # 生成新的根证书（模拟替换）
    cd "$SCRIPT_DIR"
    ./make-certs.sh --root \
        --common-name "Test CA" \
        --output-dir "$CERTS_DIR" \
        --days 365 \
        --force
    
    # 尝试使用被替换的根证书生成中间证书（应该失败）
    if ! ./make-certs.sh --intermediate test_service2 \
        --common-name "test2.service.local" \
        --root-cert "$CERTS_DIR/root/Test_CA.crt" \
        --root-key "$CERTS_DIR/root/Test_CA.key" \
        --output-dir "$CERTS_DIR" \
        2>&1 | grep -q "根证书指纹不匹配"; then
        log_fail "未能检测到根证书被替换"
    else
        log_pass "成功检测到根证书被替换"
    fi
    
    # 恢复原有根证书
    mv "$CERTS_DIR/root/Test_CA.crt.bak" "$CERTS_DIR/root/Test_CA.crt"
    mv "$CERTS_DIR/root/Test_CA.key.bak" "$CERTS_DIR/root/Test_CA.key"
}

# -----------------------------------------------------------------------------
# 测试 4: 根证书不存在时的提示
# -----------------------------------------------------------------------------
test_root_cert_not_exists() {
    log_test "测试 4: 根证书不存在时的错误提示"
    
    cd "$SCRIPT_DIR"
    if ! ./make-certs.sh --intermediate test_service \
        --common-name "test.service.local" \
        --root-cert "$CERTS_DIR/root/NonExistent.crt" \
        --root-key "$CERTS_DIR/root/NonExistent.key" \
        --output-dir "$CERTS_DIR" \
        2>&1 | grep -q "根证书文件不存在"; then
        log_fail "根证书不存在时未给出正确提示"
    else
        log_pass "正确提示根证书不存在"
    fi
}

# -----------------------------------------------------------------------------
# 测试 5: 强制要求服务名称
# -----------------------------------------------------------------------------
test_service_name_required() {
    log_test "测试 5: --intermediate 必须指定服务名称"
    
    cd "$SCRIPT_DIR"
    if ! ./make-certs.sh --intermediate \
        --common-name "test.service.local" \
        2>&1 | grep -q "生成中间证书时必须指定服务名称"; then
        log_fail "未强制要求服务名称"
    else
        log_pass "强制要求服务名称"
    fi
}

# -----------------------------------------------------------------------------
# 主测试流程
# -----------------------------------------------------------------------------
main() {
    echo "=========================================="
    echo "证书管理工具 - 根证书指纹验证测试"
    echo "=========================================="
    echo ""
    
    cleanup
    echo ""
    
    test_root_cert_fingerprint_saved
    echo ""
    
    test_intermediate_cert_with_fingerprint
    echo ""
    
    test_root_cert_replacement_detected
    echo ""
    
    test_root_cert_not_exists
    echo ""
    
    test_service_name_required
    echo ""
    
    cleanup
    echo ""
    
    echo "=========================================="
    echo "测试结果汇总"
    echo "=========================================="
    echo -e "${GREEN}通过：$TEST_PASSED${NC}"
    echo -e "${RED}失败：$TEST_FAILED${NC}"
    echo ""
    
    if [[ $TEST_FAILED -eq 0 ]]; then
        echo -e "${GREEN}所有测试通过！${NC}"
        exit 0
    else
        echo -e "${RED}部分测试失败！${NC}"
        exit 1
    fi
}

main "$@"
