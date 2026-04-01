#! /bin/bash

# =============================================================================
# 证书管理工具 - manage-certs.sh
# 用于列出、验证和管理 TLS 证书状态
# =============================================================================

set -e
script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

# -----------------------------------------------------------------------------
# 默认配置（与 make-certs.sh 保持一致）
# -----------------------------------------------------------------------------

# 组织名称（动态获取 + 降级策略）
DEFAULT_ORG_NAME=$(IocManager config PREFIX_STACK_NAME 2>/dev/null || true)
DEFAULT_ORG_NAME="${DEFAULT_ORG_NAME:-iasf}"

# 根证书固定路径配置
DEFAULT_ROOT_CERT_DIR="$(realpath "$script_dir/../root")"
DEFAULT_ROOT_CERT_NAME="$DEFAULT_ORG_NAME"
DEFAULT_ROOT_CERT="$DEFAULT_ROOT_CERT_DIR/${DEFAULT_ROOT_CERT_NAME}.crt"
DEFAULT_ROOT_KEY="$DEFAULT_ROOT_CERT_DIR/${DEFAULT_ROOT_CERT_NAME}.key"
DEFAULT_FINGERPRINT_FILE_NAME=".root_fingerprint"
DEFAULT_ROOT_FINGERPRINT_FILE="$DEFAULT_ROOT_CERT_DIR/$DEFAULT_FINGERPRINT_FILE_NAME"

# 服务器证书固定路径配置
DEFAULT_SERVER_CERT_DIR="$(realpath "$script_dir/../server")"

# -----------------------------------------------------------------------------
# 使用帮助
# -----------------------------------------------------------------------------
usage() {
    cat << EOF
用法：$0 [command] [options]

证书管理工具 - 列出、验证和管理 TLS 证书

命令:
  list                    列出所有证书（默认）
  verify                  验证所有证书的有效性
  show <service>          显示指定证书的详细信息
  check-expiry            检查即将过期的证书（30 天内）
  delete <service>        删除指定的服务器证书
  fix root                修复根证书指纹（当指纹丢失但证书和密钥完整时）

示例:
  # 列出所有证书
  $0
  
  # 验证所有证书
  $0 verify
  
  # 显示 registry 服务的证书详情
  $0 show registry
  
  # 检查即将过期的证书
  $0 check-expiry
  
  # 修复根证书目录下的指纹文件
  $0 fix root
  
  # 强制修复根证书指纹（不确认）
  $0 fix root --force
  
  # 删除 registry 服务的证书
  $0 delete registry
  
  # 强制删除证书（不确认）
  $0 delete registry --force

EOF
    exit 1
}

# -----------------------------------------------------------------------------
# 全局变量
# -----------------------------------------------------------------------------

# 命令和参数解析
COMMAND="${1:-}"
SERVICE_NAME="${2:-}"
FORCE=false

# 如果没有提供任何参数，显示帮助信息
if [[ -z "$COMMAND" ]]; then
    usage
fi

# 解析额外参数（如 --force）
if [[ "${3:-}" == "--force" ]]; then
    FORCE=true
fi

# -----------------------------------------------------------------------------
# 日志函数
# -----------------------------------------------------------------------------
log_info() {
    echo "[INFO] $1" >&2
}

log_error() {
    echo "[ERROR] $1" >&2
}

log_warn() {
    echo "[WARN] $1" >&2
}

log_success() {
    echo "[OK] $1" >&2
}

# -----------------------------------------------------------------------------
# 计算根证书指纹
# -----------------------------------------------------------------------------
calculate_root_fingerprint() {
    local cert_file="$1"
    openssl x509 -in "$cert_file" -noout -fingerprint -sha256 | cut -d'=' -f2
}

# -----------------------------------------------------------------------------
# 获取证书有效期信息
# -----------------------------------------------------------------------------
get_certificate_dates() {
    local cert_file="$1"
    
    if [[ ! -f "$cert_file" ]]; then
        return 1
    fi
    
    local start_date
    local end_date
    start_date=$(openssl x509 -in "$cert_file" -noout -startdate | cut -d= -f2)
    end_date=$(openssl x509 -in "$cert_file" -noout -enddate | cut -d= -f2)
    
    echo "$start_date|$end_date"
}

# -----------------------------------------------------------------------------
# 计算剩余天数
# -----------------------------------------------------------------------------
get_remaining_days() {
    local cert_file="$1"
    
    if [[ ! -f "$cert_file" ]]; then
        echo "-1"
        return
    fi
    
    local end_timestamp
    local now_timestamp
    end_timestamp=$(date -d "$(openssl x509 -in "$cert_file" -noout -enddate | cut -d= -f2)" +%s)
    now_timestamp=$(date +%s)
    
    local diff_seconds=$((end_timestamp - now_timestamp))
    local diff_days=$((diff_seconds / 86400))
    
    echo "$diff_days"
}

# -----------------------------------------------------------------------------
# 检查证书是否过期
# -----------------------------------------------------------------------------
is_certificate_expired() {
    local cert_file="$1"
    
    if [[ ! -f "$cert_file" ]]; then
        return 1
    fi
    
    if openssl x509 -in "$cert_file" -checkend 0 >/dev/null 2>&1; then
        return 1  # 未过期
    else
        return 0  # 已过期
    fi
}

# -----------------------------------------------------------------------------
# 检查证书是否即将过期（30 天内）
# -----------------------------------------------------------------------------
is_certificate_expiring_soon() {
    local cert_file="$1"
    local days="${2:-30}"
    local seconds=$((days * 86400))
    
    if [[ ! -f "$cert_file" ]]; then
        return 1
    fi
    
    if openssl x509 -in "$cert_file" -checkend "$seconds" >/dev/null 2>&1; then
        return 1  # 不会在指定时间内过期
    else
        return 0  # 将在指定时间内过期
    fi
}

# -----------------------------------------------------------------------------
# 验证服务器证书（返回验证结果）
# 用法：validate_server_certificate <service_name>
# 返回：RESULT_VALID (true/false), RESULT_STATUS, RESULT_MESSAGE
# -----------------------------------------------------------------------------
validate_server_certificate() {
    local service_name="$1"
    local server_cert_dir="$DEFAULT_SERVER_CERT_DIR/$service_name"
    local server_cert_file="$server_cert_dir/${service_name}.crt"
    local server_key_file="$server_cert_dir/${service_name}.key"
    local fingerprint_file="$server_cert_dir/$DEFAULT_FINGERPRINT_FILE_NAME"
    
    # 检查各个文件是否存在
    local cert_exists=false
    local key_exists=false
    local fingerprint_exists=false
    
    [[ -f "$server_cert_file" ]] && cert_exists=true
    [[ -f "$server_key_file" ]] && key_exists=true
    [[ -f "$fingerprint_file" ]] && fingerprint_exists=true
    
    # 验证证书和密钥是否匹配（如果都存在）
    local cert_key_match=false
    if $cert_exists && $key_exists; then
        if verify_cert_key_match "$server_cert_file" "$server_key_file"; then
            cert_key_match=true
        fi
    fi
    
    # 计算当前指纹并比对（如果指纹文件存在且证书密钥匹配）
    local fingerprint_matches=false
    if $cert_exists && $fingerprint_exists && $cert_key_match; then
        local saved_fingerprint
        saved_fingerprint=$(cat "$fingerprint_file")
        
        local current_fingerprint
        current_fingerprint=$(calculate_root_fingerprint "$DEFAULT_ROOT_CERT")
        
        if [[ "$saved_fingerprint" == "$current_fingerprint" ]]; then
            fingerprint_matches=true
        fi
    fi
    
    # 综合判断服务器证书状态（严格按照优先级顺序）
    if ! $cert_exists || ! $key_exists; then
        # 优先级 1：文件完整性检查
        RESULT_STATUS="文件缺失 ✗"
        RESULT_VALID=false
        RESULT_MESSAGE="证书或密钥文件缺失"
    elif ! $cert_key_match; then
        # 优先级 2：证书 - 密钥匹配性检查
        RESULT_STATUS="证书密钥不匹配 ✗"
        RESULT_VALID=false
        RESULT_MESSAGE="证书与密钥不匹配"
    elif ! $fingerprint_exists; then
        # 优先级 3：指纹文件存在性检查
        RESULT_STATUS="指纹缺失 ⚠"
        RESULT_VALID=false
        RESULT_MESSAGE="指纹文件缺失"
    elif ! $fingerprint_matches; then
        # 优先级 4：指纹一致性检查
        RESULT_STATUS="根证书不匹配 ✗"
        RESULT_VALID=false
        RESULT_MESSAGE="签名该证书的根证书已变更"
    elif ! openssl verify -CAfile "$DEFAULT_ROOT_CERT" "$server_cert_file" >/dev/null 2>&1; then
        # 优先级 5：证书链验证
        RESULT_STATUS="证书链验证失败 ✗"
        RESULT_VALID=false
        RESULT_MESSAGE="证书无法通过根证书验证"
    elif is_certificate_expired "$server_cert_file"; then
        # 优先级 6：有效期检查（已过期）
        RESULT_STATUS="已过期 ✗"
        RESULT_VALID=false
        RESULT_MESSAGE="证书已过期"
    elif is_certificate_expiring_soon "$server_cert_file"; then
        # 优先级 7：有效期检查（即将过期）
        RESULT_STATUS="即将过期 ⚠"
        RESULT_VALID=false
        RESULT_MESSAGE="证书即将过期"
    else
        # 所有检查通过
        RESULT_STATUS="有效 ✓"
        RESULT_VALID=true
        RESULT_MESSAGE=""
    fi
    
    # 导出结果为全局变量
    export RESULT_VALID RESULT_STATUS RESULT_MESSAGE
}

# -----------------------------------------------------------------------------
# 验证根证书（返回验证结果数组）
# 用法：validate_root_certificate
# 返回：RESULT_VALID (true/false), RESULT_STATUS, RESULT_MESSAGE
# -----------------------------------------------------------------------------
validate_root_certificate() {
    local root_cert_exists=false
    local root_key_exists=false
    local root_fingerprint_exists=false
    local root_fingerprint_matches=false
    local root_cert_key_match=false
    
    # 检查各个文件是否存在
    [[ -f "$DEFAULT_ROOT_CERT" ]] && root_cert_exists=true
    [[ -f "$DEFAULT_ROOT_KEY" ]] && root_key_exists=true
    [[ -f "$DEFAULT_ROOT_FINGERPRINT_FILE" ]] && root_fingerprint_exists=true
    
    # 验证证书和密钥是否匹配（如果都存在）
    if $root_cert_exists && $root_key_exists; then
        if verify_cert_key_match "$DEFAULT_ROOT_CERT" "$DEFAULT_ROOT_KEY"; then
            root_cert_key_match=true
        fi
    fi
    
    # 计算当前指纹并比对（如果指纹文件存在）
    if $root_cert_exists && $root_fingerprint_exists; then
        local current_fingerprint
        current_fingerprint=$(calculate_root_fingerprint "$DEFAULT_ROOT_CERT")
        local stored_fingerprint
        stored_fingerprint=$(cat "$DEFAULT_ROOT_FINGERPRINT_FILE")
        
        if [[ "$current_fingerprint" == "$stored_fingerprint" ]]; then
            root_fingerprint_matches=true
        fi
    fi
    
    # 综合判断根证书状态
    if ! $root_cert_exists || ! $root_key_exists; then
        RESULT_STATUS="文件缺失 ✗"
        RESULT_VALID=false
        RESULT_MESSAGE="证书或密钥文件缺失"
    elif ! $root_cert_key_match; then
        RESULT_STATUS="证书密钥不匹配 ✗"
        RESULT_VALID=false
        RESULT_MESSAGE="证书与密钥不匹配"
    elif ! $root_fingerprint_exists; then
        RESULT_STATUS="指纹缺失 ⚠"
        RESULT_VALID=false
        RESULT_MESSAGE="指纹文件缺失"
    elif ! $root_fingerprint_matches; then
        RESULT_STATUS="指纹不匹配 ✗"
        RESULT_VALID=false
        RESULT_MESSAGE="指纹校验失败"
    elif is_certificate_expired "$DEFAULT_ROOT_CERT"; then
        RESULT_STATUS="已过期 ✗"
        RESULT_VALID=false
        RESULT_MESSAGE="证书已过期"
    elif is_certificate_expiring_soon "$DEFAULT_ROOT_CERT"; then
        RESULT_STATUS="即将过期 ⚠"
        RESULT_VALID=false
        RESULT_MESSAGE="证书即将过期"
    else
        RESULT_STATUS="有效 ✓"
        RESULT_VALID=true
        RESULT_MESSAGE=""
    fi
    
    # 导出结果为全局变量
    export RESULT_VALID RESULT_STATUS RESULT_MESSAGE
}

# -----------------------------------------------------------------------------
# 列出所有证书
# -----------------------------------------------------------------------------
list_certificates() {
    
    # 验证根证书
    validate_root_certificate
    local root_status="$RESULT_STATUS"
    local root_valid="$RESULT_VALID"
    
    echo "------------------------------------------"
    echo "根证书:"
    echo "------------------------------------------"
    echo ""
    
    if [[ -f "$DEFAULT_ROOT_CERT" ]]; then
        local root_remaining
        root_remaining=$(get_remaining_days "$DEFAULT_ROOT_CERT")
        local root_fingerprint
        root_fingerprint=$(calculate_root_fingerprint "$DEFAULT_ROOT_CERT")
        
        printf "  名称：%-30s  状态：%s\n" "$DEFAULT_ROOT_CERT_NAME" "$root_status"
        printf "  路径：%-30s\n" "$DEFAULT_ROOT_CERT"
        printf "  剩余天数：%-30s\n" "$root_remaining"
        printf "  指纹：%-30s\n" "${root_fingerprint:0:64}..."
        
        # 仅在证书状态异常时显示详情
        if [[ "$root_status" != "有效 ✓" ]]; then
            echo ""
            echo "  问题详情:"
            
            # 检查并显示证书文件问题
            if [[ ! -f "$DEFAULT_ROOT_CERT" ]]; then
                echo "    ✗ 证书文件缺失：$DEFAULT_ROOT_CERT"
            fi
            
            # 检查并显示密钥文件问题
            if [[ ! -f "$DEFAULT_ROOT_KEY" ]]; then
                echo "    ✗ 密钥文件缺失：$DEFAULT_ROOT_KEY"
            fi
            
            # 检查并显示证书 - 密钥匹配问题
            if [[ -f "$DEFAULT_ROOT_CERT" ]] && [[ -f "$DEFAULT_ROOT_KEY" ]]; then
                if ! verify_cert_key_match "$DEFAULT_ROOT_CERT" "$DEFAULT_ROOT_KEY"; then
                    echo "    ✗ 证书与密钥不匹配"
                    echo "      警告：证书和密钥不是同一对密钥对"
                    echo "      建议：重新生成根证书或找回正确的密钥"
                fi
            fi
            
            # 检查并显示指纹文件问题
            if [[ -f "$DEFAULT_ROOT_CERT" ]] && [[ -f "$DEFAULT_ROOT_KEY" ]] && verify_cert_key_match "$DEFAULT_ROOT_CERT" "$DEFAULT_ROOT_KEY"; then
                # 只有在证书密钥匹配时才检查指纹问题
                if [[ ! -f "$DEFAULT_ROOT_FINGERPRINT_FILE" ]]; then
                    echo "    ⚠ 指纹文件缺失：$DEFAULT_ROOT_FINGERPRINT_FILE"
                    echo "      建议：使用 '$0 fix root' 重建指纹"
                else
                    local current_fp
                    current_fp=$(calculate_root_fingerprint "$DEFAULT_ROOT_CERT")
                    local stored_fp
                    stored_fp=$(cat "$DEFAULT_ROOT_FINGERPRINT_FILE")
                    
                    if [[ "$current_fp" != "$stored_fp" ]]; then
                        echo "    ✗ 指纹校验失败：当前指纹与保存的指纹不匹配"
                        echo "      警告：根证书可能已被替换或损坏"
                        echo "      建议：验证根证书来源，必要时重新生成"
                    fi
                fi
            fi
            
            # 检查并显示有效期问题
            if is_certificate_expired "$DEFAULT_ROOT_CERT"; then
                echo "    ✗ 证书已过期"
                echo "      建议：立即更新根证书"
            elif is_certificate_expiring_soon "$DEFAULT_ROOT_CERT"; then
                echo "    ⚠ 证书即将过期（30 天内）"
                echo "      建议：计划更新根证书"
            fi
            
            echo ""
        else
            echo ""
        fi
    else
        log_error "根证书不存在：$DEFAULT_ROOT_CERT"
        echo ""
        return 1
    fi
    
    # 列出所有服务器证书
    echo "------------------------------------------"
    echo "服务器证书:"
    echo "------------------------------------------"
    echo ""
    
    if [[ ! -d "$DEFAULT_SERVER_CERT_DIR" ]]; then
        log_info "暂无服务器证书"
        echo ""
        return 0
    fi
    
    local found=false
    for service_dir in "$DEFAULT_SERVER_CERT_DIR"/*/; do
        if [[ -d "$service_dir" ]]; then
            found=true
            local service_name
            service_name=$(basename "$service_dir")
            local cert_file="$service_dir${service_name}.crt"
            
            if [[ -f "$cert_file" ]]; then
                # 使用统一的验证函数
                validate_server_certificate "$service_name"
                local cert_status="$RESULT_STATUS"
                local cert_valid="$RESULT_VALID"
                
                local cert_remaining
                cert_remaining=$(get_remaining_days "$cert_file")
                
                printf "  服务名：%-30s  状态：%s\n" "$service_name" "$cert_status"
                printf "    路径：%-30s\n" "$cert_file"
                printf "    剩余天数：%-30s\n" "$cert_remaining"
                
                # 仅在证书状态异常时显示详情
                if [[ "$cert_status" != "有效 ✓" ]]; then
                    echo ""
                    echo "    问题详情:"
                    
                    local key_file="$service_dir${service_name}.key"
                    local fingerprint_file="$service_dir/$DEFAULT_FINGERPRINT_FILE_NAME"
                    
                    # 检查并显示证书文件问题
                    if [[ ! -f "$cert_file" ]]; then
                        echo "      ✗ 证书文件缺失：$cert_file"
                    fi
                    
                    # 检查并显示密钥文件问题
                    if [[ ! -f "$key_file" ]]; then
                        echo "      ✗ 密钥文件缺失：$key_file"
                    fi
                    
                    # 检查并显示证书 - 密钥匹配问题
                    if [[ -f "$cert_file" ]] && [[ -f "$key_file" ]]; then
                        if ! verify_cert_key_match "$cert_file" "$key_file"; then
                            echo "      ✗ 证书与密钥不匹配"
                            echo "        警告：证书和密钥不是同一对密钥对"
                            echo "        建议：重新生成该服务器证书或找回正确的密钥"
                        fi
                    fi
                    
                    # 检查并显示指纹文件问题
                    if [[ -f "$cert_file" ]] && [[ -f "$key_file" ]] && verify_cert_key_match "$cert_file" "$key_file"; then
                        if [[ ! -f "$fingerprint_file" ]]; then
                            echo "      ⚠ 指纹文件缺失：$fingerprint_file"
                            echo "        建议：运行 './make-certs.sh --server $service_name --force' 重建指纹"
                        else
                            local saved_fp
                            saved_fp=$(cat "$fingerprint_file")
                            local current_fp
                            current_fp=$(calculate_root_fingerprint "$DEFAULT_ROOT_CERT")
                            
                            if [[ "$saved_fp" != "$current_fp" ]]; then
                                echo "      ✗ 根证书指纹不匹配"
                                echo "        保存的指纹：${saved_fp:0:40}..."
                                echo "        当前指纹：${current_fp:0:40}..."
                                echo "        警告：签名该证书的根证书已变更"
                                echo "        建议：使用新根证书重新生成所有服务器证书"
                            fi
                        fi
                    fi
                    
                    # 检查并显示有效期问题
                    if is_certificate_expired "$cert_file"; then
                        echo "      ✗ 证书已过期"
                        echo "        建议：立即更新该服务器证书"
                    elif is_certificate_expiring_soon "$cert_file"; then
                        echo "      ⚠ 证书即将过期（30 天内）"
                        echo "        建议：计划更新该服务器证书"
                    fi
                    
                    echo ""
                else
                    echo ""
                fi
            fi
        fi
    done
    
    if [[ "$found" == false ]]; then
        log_info "暂无服务器证书"
        echo ""
    fi
}

# -----------------------------------------------------------------------------
# 验证所有证书
# -----------------------------------------------------------------------------
verify_all_certificates() {
    echo ""
    echo "=========================================="
    echo "       证 书 验 证"
    echo "=========================================="
    echo ""
    
    local all_valid=true
    
    # 验证根证书（使用统一的验证函数）
    printf "验证根证书... "
    validate_root_certificate
    
    if [[ "$RESULT_VALID" == true ]]; then
        log_success "有效 ✓"
    else
        log_error "$RESULT_STATUS"
        all_valid=false
        
        # 显示详细信息
        if [[ -n "$RESULT_MESSAGE" ]]; then
            log_info "  原因：$RESULT_MESSAGE"
        fi
    fi
    
    echo ""
    
    # 验证所有服务器证书（使用统一的验证函数）
    if [[ -d "$DEFAULT_SERVER_CERT_DIR" ]]; then
        for service_dir in "$DEFAULT_SERVER_CERT_DIR"/*/; do
            if [[ -d "$service_dir" ]]; then
                local service_name
                service_name=$(basename "$service_dir")
                
                printf "验证服务器证书 [%-20s]... " "$service_name"
                
                validate_server_certificate "$service_name"
                
                if [[ "$RESULT_VALID" == true ]]; then
                    log_success "有效 ✓"
                else
                    log_error "$RESULT_STATUS"
                    all_valid=false
                    
                    # 显示详细信息
                    if [[ -n "$RESULT_MESSAGE" ]]; then
                        log_info "  原因：$RESULT_MESSAGE"
                    fi
                fi
            fi
        done
    fi
    
    echo ""
    echo "------------------------------------------"
    if [[ "$all_valid" == true ]]; then
        log_success "所有证书验证通过"
    else
        log_error "存在无效或过期的证书"
        exit 1
    fi
    echo ""
}

# -----------------------------------------------------------------------------
# 显示证书详情
# -----------------------------------------------------------------------------
show_certificate_details() {
    local service_name="$1"
    
    if [[ -z "$service_name" ]]; then
        log_error "必须指定服务名称"
        usage
    fi
    
    local cert_file
    if [[ "$service_name" == "root" || "$service_name" == "root-ca" ]]; then
        cert_file="$DEFAULT_ROOT_CERT"
    else
        cert_file="$DEFAULT_SERVER_CERT_DIR/$service_name/${service_name}.crt"
    fi
    
    if [[ ! -f "$cert_file" ]]; then
        log_error "证书不存在：$cert_file"
        exit 1
    fi
    
    echo ""
    echo "=========================================="
    echo "     证 书 详 情：$service_name"
    echo "=========================================="
    echo ""
    
    openssl x509 -in "$cert_file" -text -noout
    echo ""
}

# -----------------------------------------------------------------------------
# 检查即将过期的证书
# -----------------------------------------------------------------------------
check_expiring_certificates() {
    echo ""
    echo "=========================================="
    echo "   即 将 过 期 证 书 检 查 (30 天)"
    echo "=========================================="
    echo ""
    
    local found_expiring=false
    
    # 检查根证书
    if [[ -f "$DEFAULT_ROOT_CERT" ]]; then
        # 先检查文件完整性
        local root_complete=true
        if [[ ! -f "$DEFAULT_ROOT_KEY" ]]; then
            printf "根证书：密钥文件缺失 ⚠\n"
            printf "  路径：%-30s\n" "$DEFAULT_ROOT_CERT"
            echo ""
            root_complete=false
        elif [[ ! -f "$DEFAULT_ROOT_FINGERPRINT_FILE" ]]; then
            printf "根证书：指纹文件缺失 ⚠\n"
            printf "  路径：%-30s\n" "$DEFAULT_ROOT_CERT"
            echo ""
            root_complete=false
        else
            # 验证指纹匹配性
            local current_fingerprint
            current_fingerprint=$(calculate_root_fingerprint "$DEFAULT_ROOT_CERT")
            local stored_fingerprint
            stored_fingerprint=$(cat "$DEFAULT_ROOT_FINGERPRINT_FILE")
            
            if [[ "$current_fingerprint" != "$stored_fingerprint" ]]; then
                printf "根证书：指纹不匹配 ✗\n"
                printf "  路径：%-30s\n" "$DEFAULT_ROOT_CERT"
                echo ""
                root_complete=false
            fi
        fi
        
        # 如果文件完整且指纹匹配，检查有效期
        if $root_complete; then
            if is_certificate_expiring_soon "$DEFAULT_ROOT_CERT" 30; then
                local remaining
                remaining=$(get_remaining_days "$DEFAULT_ROOT_CERT")
                printf "根证书将在 %-5s 天内过期 ⚠\n" "$remaining"
                printf "  路径：%-30s\n" "$DEFAULT_ROOT_CERT"
                echo ""
                found_expiring=true
            fi
        fi
    fi
    
    # 检查服务器证书
    if [[ -d "$DEFAULT_SERVER_CERT_DIR" ]]; then
        for service_dir in "$DEFAULT_SERVER_CERT_DIR"/*/; do
            if [[ -d "$service_dir" ]]; then
                local service_name
                service_name=$(basename "$service_dir")
                local cert_file="$service_dir${service_name}.crt"
                
                if [[ -f "$cert_file" ]]; then
                    if is_certificate_expiring_soon "$cert_file" 30; then
                        local remaining
                        remaining=$(get_remaining_days "$cert_file")
                        printf "服务器证书 [%-20s] 将在 %-5s 天内过期\n" "$service_name" "$remaining"
                        printf "  路径：%-30s\n" "$cert_file"
                        echo ""
                        found_expiring=true
                    fi
                fi
            fi
        done
    fi
    
    if [[ "$found_expiring" == false ]]; then
        log_success "没有即将过期的证书（30 天内）"
    else
        log_warn "发现即将过期的证书，请及时更新"
    fi
    echo ""
}

# -----------------------------------------------------------------------------
# 删除指定证书
# -----------------------------------------------------------------------------
delete_certificate() {
    local service_name="$1"
    local force="$2"
    
    if [[ -z "$service_name" ]]; then
        log_error "必须指定服务名称"
        usage
    fi
    
    # 不允许删除根证书
    if [[ "$service_name" == "root" || "$service_name" == "root-ca" ]]; then
        log_error "禁止删除根证书！"
        log_error "如需删除根证书，请手动操作：rm -rf $DEFAULT_ROOT_CERT_DIR/*"
        exit 1
    fi
    
    local cert_dir="$DEFAULT_SERVER_CERT_DIR/$service_name"
    local cert_file="$cert_dir/${service_name}.crt"
    local key_file="$cert_dir/${service_name}.key"
    local fingerprint_file="$cert_dir/$DEFAULT_FINGERPRINT_FILE_NAME"
    
    # 检查证书是否存在
    if [[ ! -f "$cert_file" ]]; then
        log_error "证书不存在：$cert_file"
        exit 1
    fi
    
    # 显示将要删除的文件
    echo ""
    echo "=========================================="
    echo "     即将删除证书：$service_name"
    echo "=========================================="
    echo ""
    printf "证书目录：%-50s\n" "$cert_dir"
    echo ""
    echo "将要删除的文件："
    [[ -f "$cert_file" ]] && printf "  ✓ %s\n" "$cert_file"
    [[ -f "$key_file" ]] && printf "  ✓ %s\n" "$key_file"
    [[ -f "$fingerprint_file" ]] && printf "  ✓ %s\n" "$fingerprint_file"
    echo ""
    
    # 询问确认（除非使用 --force）
    if [[ "$force" != true ]]; then
        read -p "确认删除？[y/N]: " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "已取消删除操作"
            echo ""
            return 0
        fi
    fi
    
    # 执行删除
    log_info "正在删除证书文件..."
    rm -rf "$cert_dir"
    
    log_success "证书已成功删除：$service_name"
    echo ""
}

# -----------------------------------------------------------------------------
# 验证证书和密钥是否匹配
# -----------------------------------------------------------------------------
verify_cert_key_match() {
    local cert_file="$1"
    local key_file="$2"
    
    if [[ ! -f "$cert_file" ]] || [[ ! -f "$key_file" ]]; then
        return 1
    fi
    
    # 提取证书的公钥哈希
    local cert_modulus
    cert_modulus=$(openssl x509 -noout -modulus -in "$cert_file" 2>/dev/null | openssl md5)
    
    # 提取私钥的公钥哈希
    local key_modulus
    key_modulus=$(openssl rsa -noout -modulus -in "$key_file" 2>/dev/null | openssl md5)
    
    # 比较两者是否一致
    if [[ "$cert_modulus" == "$key_modulus" ]]; then
        return 0
    else
        return 1
    fi
}

# -----------------------------------------------------------------------------
# 修复根证书指纹
# -----------------------------------------------------------------------------
fix_root_fingerprint() {
    local force="${1:-false}"
    
    echo ""
    echo "=========================================="
    echo "       修 复 根 证 书 指 纹"
    echo "=========================================="
    echo ""
    
    # 检查根证书文件
    if [[ ! -f "$DEFAULT_ROOT_CERT" ]]; then
        log_error "根证书不存在：$DEFAULT_ROOT_CERT"
        echo ""
        return 1
    fi
    
    # 检查根密钥文件
    if [[ ! -f "$DEFAULT_ROOT_KEY" ]]; then
        log_error "根密钥不存在：$DEFAULT_ROOT_KEY"
        echo ""
        return 1
    fi
    
    # 验证证书和密钥是否匹配
    if ! verify_cert_key_match "$DEFAULT_ROOT_CERT" "$DEFAULT_ROOT_KEY"; then
        log_error "根证书与根密钥不匹配！无法重建指纹"
        echo ""
        return 1
    fi
    
    # 计算当前根证书指纹
    local current_fingerprint
    current_fingerprint=$(calculate_root_fingerprint "$DEFAULT_ROOT_CERT")
    
    # 检查指纹文件是否存在
    if [[ -f "$DEFAULT_ROOT_FINGERPRINT_FILE" ]]; then
        local stored_fingerprint
        stored_fingerprint=$(cat "$DEFAULT_ROOT_FINGERPRINT_FILE")
        
        if [[ "$current_fingerprint" == "$stored_fingerprint" ]]; then
            log_success "指纹文件已存在且匹配，无需修复"
            echo ""
            return 0
        else
            log_warn "指纹文件存在但不匹配，将覆盖现有指纹"
        fi
    else
        log_info "指纹文件不存在，将创建新指纹文件"
    fi
    
    # 询问确认（除非使用 --force）
    if [[ "$force" != true ]]; then
        read -p "确认重建根证书指纹？[y/N]: " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "已取消修复操作"
            echo ""
            return 0
        fi
    fi
    
    # 写入指纹文件（先比对后写入）
    if [[ -f "$DEFAULT_ROOT_FINGERPRINT_FILE" ]]; then
        local existing_fingerprint
        existing_fingerprint=$(cat "$DEFAULT_ROOT_FINGERPRINT_FILE")
        
        if [[ "$current_fingerprint" == "$existing_fingerprint" ]]; then
            log_info "指纹文件内容已匹配，跳过写入"
            echo ""
            return 0
        fi
    fi
    
    # 创建或更新指纹文件
    echo "$current_fingerprint" > "$DEFAULT_ROOT_FINGERPRINT_FILE"
    chmod 600 "$DEFAULT_ROOT_FINGERPRINT_FILE"
    
    log_success "根证书指纹已成功重建"
    printf "  指纹：%s\n" "${current_fingerprint:0:64}..."
    echo ""
}

# -----------------------------------------------------------------------------
# 修复证书指纹（仅支持根证书）
# -----------------------------------------------------------------------------
fix_certificate() {
    local service_name="${1:-}"
    
    # 如果指定了服务名但不是 root，提示错误
    if [[ -n "$service_name" && "$service_name" != "root" && "$service_name" != "root-ca" ]]; then
        log_error "fix 命令仅支持修复根证书指纹"
        echo ""
        log_info "使用方法：$0 fix root"
        echo ""
        return 1
    fi
    
    fix_root_fingerprint "$FORCE"
}

# -----------------------------------------------------------------------------
# 主函数
# -----------------------------------------------------------------------------
main() {
    case $COMMAND in
        list)
            list_certificates
            ;;
        verify)
            verify_all_certificates
            ;;
        show)
            show_certificate_details "$SERVICE_NAME"
            ;;
        check-expiry)
            check_expiring_certificates
            ;;
        delete)
            delete_certificate "$SERVICE_NAME" "$FORCE"
            ;;
        fix)
            fix_certificate "$SERVICE_NAME"
            ;;
        help|-h|--help)
            usage
            ;;
        *)
            log_error "未知命令：$COMMAND"
            usage
            ;;
    esac
}

# 执行主函数
main "$@"
