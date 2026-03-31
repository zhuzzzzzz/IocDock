#! /bin/bash

# =============================================================================
# 证书管理工具 - make-certs.sh
# 用于生成和管理 TLS 证书（根证书和中间证书）
# =============================================================================

set -e
script_abs=$(readlink -f "$0")
script_dir=$(dirname $script_abs)

# -----------------------------------------------------------------------------
# 默认配置
# -----------------------------------------------------------------------------
DEFAULT_ALGORITHM="RSA"
DEFAULT_KEY_LENGTH=4096
DEFAULT_HASH_ALGORITHM="sha256"
DEFAULT_ROOT_DAYS=3650
DEFAULT_SERVER_DAYS=1825
DEFAULT_COUNTRY="CN"
DEFAULT_STATE="Guangdong"
DEFAULT_LOCALITY="Shenzhen"
DEFAULT_ORGANIZATION="IASF"
DEFAULT_ORGANIZATIONAL_UNIT="ControlSystem"

# 根证书固定路径配置
DEFAULT_ROOT_CERT_DIR="$script_dir/../certs/root"
DEFAULT_ROOT_CERT_NAME="root-ca"
DEFAULT_ROOT_CERT="$DEFAULT_ROOT_CERT_DIR/${DEFAULT_ROOT_CERT_NAME}.crt"
DEFAULT_ROOT_KEY="$DEFAULT_ROOT_CERT_DIR/${DEFAULT_ROOT_CERT_NAME}.key"
DEFAULT_ROOT_FINGERPRINT_FILE="$DEFAULT_ROOT_CERT_DIR/.root_fingerprint"

# 服务器证书固定路径配置
DEFAULT_SERVER_CERT_DIR="$script_dir/../certs/server"

# -----------------------------------------------------------------------------
# 全局变量
# -----------------------------------------------------------------------------
CERT_MODE=""
COMMON_NAME=""
SERVICE_NAME=""
ALGORITHM="$DEFAULT_ALGORITHM"
KEY_LENGTH="$DEFAULT_KEY_LENGTH"
HASH_ALGORITHM="$DEFAULT_HASH_ALGORITHM"
DAYS=""
SUBJECT_ALT_NAMES=""
FORCE=false

# 证书信息
COUNTRY="$DEFAULT_COUNTRY"
STATE="$DEFAULT_STATE"
LOCALITY="$DEFAULT_LOCALITY"
ORGANIZATION="$DEFAULT_ORGANIZATION"
ORGANIZATIONAL_UNIT="$DEFAULT_ORGANIZATIONAL_UNIT"

# -----------------------------------------------------------------------------
# 使用帮助
# -----------------------------------------------------------------------------
usage() {
    cat << EOF
用法：$0 [选项]

证书管理工具 - 生成和管理 TLS 证书

模式选择:
  --root                    生成自签名根证书
  --server <service>        生成服务器证书（需要指定服务名称）

必需参数:
  --common-name <CN>        证书通用名称（Common Name）

可选参数:
  --algorithm <alg>         加密算法：RSA, EC, DSA（默认：$DEFAULT_ALGORITHM）
  --key-length <bits>       密钥长度（默认：$DEFAULT_KEY_LENGTH）
  --hash-algorithm <alg>    哈希算法：sha256, sha384, sha512（默认：$DEFAULT_HASH_ALGORITHM）
  --days <num>              证书有效期天数（根证书默认：$DEFAULT_ROOT_DAYS，服务器证书默认：$DEFAULT_SERVER_DAYS）
  --subject-alt-names <SANs> 主题备用名称，逗号分隔（例如：DNS:example.com,DNS:www.example.com）
  --force                   覆盖已存在的证书文件

证书信息:
  --country <code>          国家代码（默认：$DEFAULT_COUNTRY）
  --state <province>        省份（默认：$DEFAULT_STATE）
  --locality <city>         城市（默认：$DEFAULT_LOCALITY）
  --organization <org>      组织名称（默认：$DEFAULT_ORGANIZATION）
  --organizational-unit <unit> 部门名称（默认：$DEFAULT_ORGANIZATIONAL_UNIT）

示例:
  # 生成自签名根证书
  $0 --root --common-name "My Root CA"
  
  # 生成服务器证书（自动使用项目内的根证书）
  $0 --server registry \
     --common-name "registry.example.com"
  
  # 生成带 SAN 的服务器证书
  $0 --server grafana \
     --common-name "grafana.example.com" \
     --subject-alt-names "DNS:grafana.example.com,DNS:monitor.example.com" \
     --days 730

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

# -----------------------------------------------------------------------------
# 解析命令行参数
# -----------------------------------------------------------------------------
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --root)
                CERT_MODE="root"
                shift
                ;;
            --server)
                CERT_MODE="server"
                # 检查是否提供了服务名称参数
                if [[ -z "$2" || "$2" =~ ^-- ]]; then
                    log_error "生成服务器证书时必须指定服务名称"
                    usage
                fi
                SERVICE_NAME="$2"
                shift 2
                ;;
            --common-name)
                COMMON_NAME="$2"
                shift 2
                ;;
            --algorithm)
                ALGORITHM="$2"
                shift 2
                ;;
            --key-length)
                KEY_LENGTH="$2"
                shift 2
                ;;
            --hash-algorithm)
                HASH_ALGORITHM="$2"
                shift 2
                ;;
            --days)
                DAYS="$2"
                shift 2
                ;;
            --subject-alt-names)
                SUBJECT_ALT_NAMES="$2"
                shift 2
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --country)
                COUNTRY="$2"
                shift 2
                ;;
            --state)
                STATE="$2"
                shift 2
                ;;
            --locality)
                LOCALITY="$2"
                shift 2
                ;;
            --organization)
                ORGANIZATION="$2"
                shift 2
                ;;
            --organizational-unit)
                ORGANIZATIONAL_UNIT="$2"
                shift 2
                ;;
            --help|-h)
                usage
                ;;
            *)
                log_error "未知参数：$1"
                usage
                ;;
        esac
    done
}

# -----------------------------------------------------------------------------
# 验证参数
# -----------------------------------------------------------------------------
validate_params() {
    # 验证证书模式
    if [[ -z "$CERT_MODE" ]]; then
        log_error "必须指定证书模式：--root 或 --server"
        usage
    fi
    
    # 验证 Common Name
    if [[ -z "$COMMON_NAME" ]]; then
        log_error "必须指定 --common-name 参数"
        usage
    fi
    
    # 验证服务器证书参数
    if [[ "$CERT_MODE" == "server" ]]; then
        if [[ -z "$SERVICE_NAME" ]]; then
            log_error "生成服务器证书时必须指定服务名称"
            usage
        fi
        
        # 使用默认的根证书路径（项目目录内固定路径）
        if [[ ! -f "$DEFAULT_ROOT_CERT" ]]; then
            log_error "根证书文件不存在：$DEFAULT_ROOT_CERT"
            log_error "请先使用 --root 模式生成根证书"
            exit 1
        fi
        if [[ ! -f "$DEFAULT_ROOT_KEY" ]]; then
            log_error "根证书私钥文件不存在：$DEFAULT_ROOT_KEY"
            exit 1
        fi
        
        # 验证根证书指纹匹配性（防止使用不匹配的根证书生成服务器证书）
        verify_root_certificate_for_generation
    fi
    
    # 验证加密算法
    if [[ "$ALGORITHM" != "RSA" && "$ALGORITHM" != "EC" && "$ALGORITHM" != "DSA" ]]; then
        log_error "不支持的加密算法：$ALGORITHM（支持：RSA, EC, DSA）"
        exit 1
    fi
    
    # 验证哈希算法
    if [[ "$HASH_ALGORITHM" != "sha256" && "$HASH_ALGORITHM" != "sha384" && "$HASH_ALGORITHM" != "sha512" ]]; then
        log_error "不支持的哈希算法：$HASH_ALGORITHM（支持：sha256, sha384, sha512）"
        exit 1
    fi
    
    # 设置默认有效期
    if [[ -z "$DAYS" ]]; then
        if [[ "$CERT_MODE" == "root" ]]; then
            DAYS=$DEFAULT_ROOT_DAYS
        else
            DAYS=$DEFAULT_SERVER_DAYS
        fi
    fi

}

# 创建目录结构
# -----------------------------------------------------------------------------
setup_directories() {
    local cert_dir
    
    if [[ "$CERT_MODE" == "root" ]]; then
        # 根证书使用统一定义的目录
        cert_dir="$DEFAULT_ROOT_CERT_DIR"
    else
        cert_dir="$DEFAULT_SERVER_CERT_DIR/$SERVICE_NAME"
    fi
    
    mkdir -p "$cert_dir"
    echo "$cert_dir"
}

# -----------------------------------------------------------------------------
# 检查文件是否存在
# -----------------------------------------------------------------------------
check_existing_files() {
    local cert_file="$1"
    local key_file="$2"
    
    if [[ -f "$cert_file" || -f "$key_file" ]]; then
        if [[ "$FORCE" != true ]]; then
            log_error "证书文件已存在，使用 --force 参数覆盖"
            exit 1
        else
            log_info "删除已存在的证书文件"
            rm -f "$cert_file" "$key_file"
        fi
    fi
}

# -----------------------------------------------------------------------------
# 生成 OpenSSL 配置文件（根证书 - CA 证书）
# -----------------------------------------------------------------------------
generate_root_openssl_config() {
    local config_file="$1"
    local san_config="${2:-}"
    
    cat > "$config_file" << EOF
[req]
default_bits = $KEY_LENGTH
prompt = no
default_md = $HASH_ALGORITHM
distinguished_name = dn
x509_extensions = v3_ca

[dn]
C = $COUNTRY
ST = $STATE
L = $LOCALITY
O = $ORGANIZATION
OU = $ORGANIZATIONAL_UNIT
CN = $COMMON_NAME

[v3_ca]
# 基本约束：标记为 CA 证书
basicConstraints = critical, CA:TRUE, pathlen:1
# 密钥用途：证书签名、CRL 签名
keyUsage = critical, keyCertSign, cRLSign
# 扩展密钥用途：不适用于服务器/客户端认证
extendedKeyUsage = critical, serverAuth, clientAuth, codeSigning, emailProtection
# 主题密钥标识符
subjectKeyIdentifier = hash
$([[ -n "$san_config" ]] && echo "subjectAltName = $san_config")
EOF
}

# -----------------------------------------------------------------------------
# 生成 OpenSSL 配置文件（服务器证书）
# 参数：$1=config_file, $2=san_config (可选)
# -----------------------------------------------------------------------------
generate_server_openssl_config() {
    local config_file="$1"
    local san_config="${2:-}"
    
    cat > "$config_file" << EOF
[req]
default_bits = $KEY_LENGTH
prompt = no
default_md = $HASH_ALGORITHM
distinguished_name = dn

[dn]
C = $COUNTRY
ST = $STATE
L = $LOCALITY
O = $ORGANIZATION
OU = $ORGANIZATIONAL_UNIT
CN = $COMMON_NAME

[v3_server]
# 基本约束：CA:FALSE 表示不能签发其他证书
basicConstraints = critical, CA:FALSE
# 密钥用途：数字签名、密钥加密
keyUsage = critical, digitalSignature, keyEncipherment
# 扩展密钥用途：服务器认证、客户端认证
extendedKeyUsage = serverAuth, clientAuth
# 主题密钥标识符
subjectKeyIdentifier = hash
# 授权密钥标识符（指向签发者）
authorityKeyIdentifier = keyid,issuer
$([[ -n "$san_config" ]] && echo "subjectAltName = $san_config")
EOF
}

# -----------------------------------------------------------------------------
# 计算根证书指纹
# -----------------------------------------------------------------------------
calculate_root_fingerprint() {
    local cert_file="$1"
    openssl x509 -in "$cert_file" -noout -fingerprint -sha256 | cut -d'=' -f2
}

# -----------------------------------------------------------------------------
# 验证根证书指纹（生成中间证书前检查）
# -----------------------------------------------------------------------------
verify_root_certificate_for_generation() {
    # 如果全局指纹文件不存在，说明这是第一次生成证书，无需验证
    if [[ ! -f "$DEFAULT_ROOT_FINGERPRINT_FILE" ]]; then
        return 0
    fi
    
    # 读取保存的指纹
    local saved_fingerprint
    saved_fingerprint=$(cat "$DEFAULT_ROOT_FINGERPRINT_FILE")
    
    # 计算当前根证书的指纹
    local current_fingerprint
    current_fingerprint=$(calculate_root_fingerprint "$DEFAULT_ROOT_CERT")
    
    # 比较指纹
    if [[ "$saved_fingerprint" != "$current_fingerprint" ]]; then
        log_error "根证书指纹不匹配！"
        log_error "当前的根证书与之前生成证书时使用的根证书不一致"
        log_error "已保存的指纹：$saved_fingerprint"
        log_error "当前指纹：$current_fingerprint"
        log_error "\n原因可能是："
        log_error "  1. 根证书已被重新生成或替换"
        log_error "  2. 所有现有的服务器证书已失效"
        log_error "\n解决方案："
        log_error "  1. 删除旧的服务器证书：rm -rf $DEFAULT_SERVER_CERT_DIR/*"
        log_error "  2. 使用当前根证书重新生成所有服务器证书"
        exit 1
    fi
    
    log_info "根证书指纹验证通过"
}

# -----------------------------------------------------------------------------
# 保存根证书指纹
# -----------------------------------------------------------------------------
save_root_fingerprint() {
    local cert_file="$1"
    
    # 如果指纹文件已存在，说明要覆盖旧的指纹，警告用户中间证书将失效
    if [[ -f "$DEFAULT_ROOT_FINGERPRINT_FILE" ]]; then
        local old_fingerprint
        old_fingerprint=$(cat "$DEFAULT_ROOT_FINGERPRINT_FILE")
        local new_fingerprint
        new_fingerprint=$(calculate_root_fingerprint "$cert_file")
        
        if [[ "$old_fingerprint" != "$new_fingerprint" ]]; then
            log_info "警告：检测到新的根证书，旧的根证书指纹将被覆盖"
            log_info "所有使用旧根证书签发的中间证书将失效！"
            log_info "旧指纹：$old_fingerprint"
            log_info "新指纹：$new_fingerprint"
        fi
    fi
    
    local fingerprint
    fingerprint=$(calculate_root_fingerprint "$cert_file")
    
    echo "$fingerprint" > "$DEFAULT_ROOT_FINGERPRINT_FILE"
    chmod 644 "$DEFAULT_ROOT_FINGERPRINT_FILE"
    
    log_info "已保存根证书指纹：$fingerprint"
}

# -----------------------------------------------------------------------------
# 生成根证书
# -----------------------------------------------------------------------------
generate_root_certificate() {
    local cert_dir
    cert_dir=$(setup_directories)
    
    # 根证书使用固定的名称（不依赖 COMMON_NAME）
    local cert_name="$DEFAULT_ROOT_CERT_NAME"
    local cert_file="$cert_dir/${cert_name}.crt"
    local key_file="$cert_dir/${cert_name}.key"
    
    # 使用 mktemp 创建安全的临时文件
    local config_file
    config_file=$(mktemp /tmp/openssl_root_conf.XXXXXX)
    
    log_info "开始生成根证书"
    log_info "证书目录：$cert_dir"
    log_info "证书名称：$cert_name"
    
    # 检查现有文件
    check_existing_files "$cert_file" "$key_file"
    
    # 生成 OpenSSL 配置（带 CA 扩展）
    local san_config="$SUBJECT_ALT_NAMES"
    generate_root_openssl_config "$config_file" "$san_config"
    
    # 生成根证书
    openssl req \
        -x509 \
        -newkey $ALGORITHM:$KEY_LENGTH \
        -nodes \
        -$HASH_ALGORITHM \
        -days $DAYS \
        -keyout "$key_file" \
        -out "$cert_file" \
        -config "$config_file" \
        -extensions v3_ca
    
    # 清理临时配置文件
    rm -f "$config_file"
    
    log_info "根证书生成成功"
    log_info "证书文件：$cert_file"
    log_info "私钥文件：$key_file"
    
    # 保存根证书指纹
    save_root_fingerprint "$cert_file"
    
    # 显示证书信息
    display_certificate_info "$cert_file"
}

# -----------------------------------------------------------------------------
# 生成服务器证书
# -----------------------------------------------------------------------------
generate_server_certificate() {
    local cert_dir
    cert_dir=$(setup_directories)
    
    # 服务器证书使用服务名称作为文件名（不依赖 COMMON_NAME）
    local cert_name="$SERVICE_NAME"
    local cert_file="$cert_dir/${cert_name}.crt"
    local key_file="$cert_dir/${cert_name}.key"
    
    # 使用 mktemp 创建安全的临时文件（防止竞态条件攻击）
    local csr_file
    csr_file=$(mktemp /tmp/server_csr.XXXXXX)
    local config_file
    config_file=$(mktemp /tmp/openssl_server_conf.XXXXXX)
    
    log_info "开始生成服务器证书"
    log_info "服务名称：$SERVICE_NAME"
    log_info "证书目录：$cert_dir"
    log_info "证书名称：$cert_name"
    
    # 检查现有文件
    check_existing_files "$cert_file" "$key_file"
    
    # 生成 OpenSSL 配置（包含 CSR 和扩展）
    local san_config="$SUBJECT_ALT_NAMES"
    generate_server_openssl_config "$config_file" "$san_config"
    
    # 生成 CSR
    openssl req \
        -new \
        -newkey $ALGORITHM:$KEY_LENGTH \
        -nodes \
        -$HASH_ALGORITHM \
        -keyout "$key_file" \
        -out "$csr_file" \
        -config "$config_file"
    
    # 使用根证书签发服务器证书（应用 v3_server 扩展配置）
    log_info "正在使用根证书签发服务器证书..."
    openssl x509 \
        -req \
        -in "$csr_file" \
        -CA "$DEFAULT_ROOT_CERT" \
        -CAkey "$DEFAULT_ROOT_KEY" \
        -CAcreateserial \
        -out "$cert_file" \
        -days $DAYS \
        -$HASH_ALGORITHM \
        -extfile "$config_file" \
        -extensions v3_server
    
    # 清理临时文件（csr 和 config）
    rm -f "$csr_file" "$config_file"
    
    log_info "服务器证书签发成功"
    log_info "证书文件：$cert_file"
    log_info "私钥文件：$key_file"
    
    # 显示证书信息
    display_certificate_info "$cert_file"
}

# -----------------------------------------------------------------------------
# 显示证书信息
# -----------------------------------------------------------------------------
display_certificate_info() {
    local cert_file="$1"
    
    if [[ -f "$cert_file" ]]; then
        log_info "证书详细信息:"
        openssl x509 -in "$cert_file" -text -noout | head -30
    fi
}

# -----------------------------------------------------------------------------
# 主函数
# -----------------------------------------------------------------------------
main() {
    parse_args "$@"
    validate_params
    
    log_info "证书生成配置:"
    log_info "  模式：$CERT_MODE"
    log_info "  通用名称：$COMMON_NAME"
    log_info "  加密算法：$ALGORITHM ($KEY_LENGTH bits)"
    log_info "  哈希算法：$HASH_ALGORITHM"
    log_info "  有效期：$DAYS 天"
    [[ -n "$SUBJECT_ALT_NAMES" ]] && log_info "  SAN: $SUBJECT_ALT_NAMES"
    
    case $CERT_MODE in
        root)
            generate_root_certificate
            ;;
        server)
            generate_server_certificate
            ;;
    esac
    
    log_info "证书生成完成!"
}

# 执行主函数
main "$@"
