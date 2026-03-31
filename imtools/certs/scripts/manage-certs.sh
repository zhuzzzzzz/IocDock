#! /bin/bash

# =============================================================================
# 证书管理工具 - manage-certs.sh
# 用于列出、验证和管理 TLS 证书状态
# =============================================================================

set -e
script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

# -----------------------------------------------------------------------------
# 默认配置
# -----------------------------------------------------------------------------
DEFAULT_ROOT_CERT_DIR="$script_dir/../certs/root"
DEFAULT_ROOT_CERT_NAME="root-ca"
DEFAULT_SERVER_CERT_DIR="$script_dir/../certs/server"
DEFAULT_ROOT_CERT="$DEFAULT_ROOT_CERT_DIR/${DEFAULT_ROOT_CERT_NAME}.crt"
DEFAULT_ROOT_KEY="$DEFAULT_ROOT_CERT_DIR/${DEFAULT_ROOT_CERT_NAME}.key"
DEFAULT_ROOT_FINGERPRINT_FILE="$DEFAULT_ROOT_CERT_DIR/.root_fingerprint"

# -----------------------------------------------------------------------------
# 全局变量
# -----------------------------------------------------------------------------
COMMAND="${1:-list}"
SERVICE_NAME="$2"

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

示例:
  # 列出所有证书
  $0
  
  # 验证所有证书
  $0 verify
  
  # 显示 registry 服务的证书详情
  $0 show registry
  
  # 检查即将过期的证书
  $0 check-expiry

EOF
    exit 1
}

# -----------------------------------------------------------------------------
# 日志函数
# -----------------------------------------------------------------------------
log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

log_warn() {
    echo "[WARN] $1" >&2
}

log_success() {
    echo "[OK] $1"
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
# 验证服务器证书
# -----------------------------------------------------------------------------
verify_server_certificate() {
    local service_name="$1"
    local server_cert_dir="$DEFAULT_SERVER_CERT_DIR/$service_name"
    local server_cert_file="$server_cert_dir/${service_name}.crt"
    local stored_fingerprint_file="$server_cert_dir/.root_fingerprint"
    
    # 检查服务器证书是否存在
    if [[ ! -f "$server_cert_file" ]]; then
        return 1
    fi
    
    # 检查是否保存了根证书指纹
    if [[ ! -f "$stored_fingerprint_file" ]]; then
        return 1
    fi
    
    # 读取保存的根证书指纹
    local saved_fingerprint
    saved_fingerprint=$(cat "$stored_fingerprint_file")
    
    # 计算当前根证书的指纹
    local current_fingerprint
    current_fingerprint=$(calculate_root_fingerprint "$DEFAULT_ROOT_CERT")
    
    # 比较指纹
    if [[ "$saved_fingerprint" != "$current_fingerprint" ]]; then
        return 1
    fi
    
    # 验证服务器证书本身的有效性
    if ! openssl verify -CAfile "$DEFAULT_ROOT_CERT" "$server_cert_file" >/dev/null 2>&1; then
        return 1
    fi
    
    return 0
}

# -----------------------------------------------------------------------------
# 列出所有证书
# -----------------------------------------------------------------------------
list_certificates() {
    echo ""
    echo "=========================================="
    echo "         证 书 列 表"
    echo "=========================================="
    echo ""
    
    # 检查根证书
    if [[ -f "$DEFAULT_ROOT_CERT" ]]; then
        local root_dates
        root_dates=$(get_certificate_dates "$DEFAULT_ROOT_CERT")
        local root_start
        root_start=$(echo "$root_dates" | cut -d'|' -f1)
        local root_end
        root_end=$(echo "$root_dates" | cut -d'|' -f2)
        local root_remaining
        root_remaining=$(get_remaining_days "$DEFAULT_ROOT_CERT")
        local root_fingerprint
        root_fingerprint=$(calculate_root_fingerprint "$DEFAULT_ROOT_CERT")
        
        printf "根证书:\n"
        printf "  名称：%-30s\n" "$DEFAULT_ROOT_CERT_NAME"
        printf "  路径：%-30s\n" "$DEFAULT_ROOT_CERT"
        printf "  有效期：%s 至 %s\n" "$root_start" "$root_end"
        printf "  剩余天数：%-30s\n" "$root_remaining"
        printf "  指纹：%-30s\n" "${root_fingerprint:0:64}..."
        printf "  状态："
        
        if is_certificate_expired "$DEFAULT_ROOT_CERT"; then
            log_error "已过期 ✗"
        elif is_certificate_expiring_soon "$DEFAULT_ROOT_CERT"; then
            log_warn "即将过期 ⚠"
        else
            log_success "有效 ✓"
        fi
        echo ""
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
                local cert_dates
                cert_dates=$(get_certificate_dates "$cert_file")
                local cert_start
                cert_start=$(echo "$cert_dates" | cut -d'|' -f1)
                local cert_end
                cert_end=$(echo "$cert_dates" | cut -d'|' -f2)
                local cert_remaining
                cert_remaining=$(get_remaining_days "$cert_file")
                
                printf "  服务名：%-25s\n" "$service_name"
                printf "    路径：%-30s\n" "$cert_file"
                printf "    有效期：%s 至 %s\n" "$cert_start" "$cert_end"
                printf "    剩余天数：%-30s\n" "$cert_remaining"
                printf "    状态："
                
                if ! verify_server_certificate "$service_name"; then
                    log_error "无效（根证书不匹配）✗"
                elif is_certificate_expired "$cert_file"; then
                    log_error "已过期 ✗"
                elif is_certificate_expiring_soon "$cert_file"; then
                    log_warn "即将过期 ⚠"
                else
                    log_success "有效 ✓"
                fi
                echo ""
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
    
    # 验证根证书
    if [[ -f "$DEFAULT_ROOT_CERT" ]]; then
        printf "验证根证书... "
        
        if is_certificate_expired "$DEFAULT_ROOT_CERT"; then
            log_error "已过期 ✗"
            all_valid=false
        else
            log_success "有效 ✓"
        fi
    else
        log_error "根证书不存在"
        all_valid=false
    fi
    
    echo ""
    
    # 验证所有中间证书
    if [[ -d "$DEFAULT_INTERMEDIATE_CERT_DIR" ]]; then
        for service_dir in "$DEFAULT_INTERMEDIATE_CERT_DIR"/*/; do
            if [[ -d "$service_dir" ]]; then
                local service_name
                service_name=$(basename "$service_dir")
                local cert_file="$service_dir${service_name}.crt"
                
                if [[ -f "$cert_file" ]]; then
                    printf "验证中间证书 [%-20s]... " "$service_name"
                    
                    if ! verify_intermediate_certificate "$service_name"; then
                        log_error "无效 ✗"
                        all_valid=false
                    elif is_certificate_expired "$cert_file"; then
                        log_error "已过期 ✗"
                        all_valid=false
                    else
                        log_success "有效 ✓"
                    fi
                fi
            fi
        done
    fi
    
    # 验证所有服务器证书
    if [[ -d "$DEFAULT_SERVER_CERT_DIR" ]]; then
        for service_dir in "$DEFAULT_SERVER_CERT_DIR"/*/; do
            if [[ -d "$service_dir" ]]; then
                local service_name
                service_name=$(basename "$service_dir")
                local cert_file="$service_dir${service_name}.crt"
                
                if [[ -f "$cert_file" ]]; then
                    printf "验证服务器证书 [%-20s]... " "$service_name"
                    
                    if ! verify_server_certificate "$service_name"; then
                        log_error "无效 ✗"
                        all_valid=false
                    elif is_certificate_expired "$cert_file"; then
                        log_error "已过期 ✗"
                        all_valid=false
                    else
                        log_success "有效 ✓"
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
        if is_certificate_expiring_soon "$DEFAULT_ROOT_CERT" 30; then
            local remaining
            remaining=$(get_remaining_days "$DEFAULT_ROOT_CERT")
            printf "根证书将在 %-5s 天内过期\n" "$remaining"
            printf "  路径：%-30s\n" "$DEFAULT_ROOT_CERT"
            echo ""
            found_expiring=true
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
