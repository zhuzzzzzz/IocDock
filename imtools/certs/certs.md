#### 构建证书链

[参考 docker daemon 文档链接](https://docs.docker.com/engine/security/protect-access/#use-tls-https-to-protect-the-docker-daemon-socket)


1. 创建根证书私钥   
  ``` openssl genrsa -aes256 -out ca-key.pem 4096 ```

2. 生成自签名的根证书   
  ``` openssl req -new -x509 -days 365 -key ca-key.pem -sha256 -out ca.pem ```

3. 创建服务器证书私钥   
  ``` openssl genrsa -out server-key.pem 4096 ```

4. 生成服务器证书签名请求(certificate signing request, CSR)   
  ``` openssl req -sha256 -new -key server-key.pem -out server.csr ```

5. 生成证书扩展配置文件   
  ``` echo subjectAltName = DNS:$HOST,IP:10.10.10.20,IP:127.0.0.1 >> extfile.cnf ```   
  ``` echo keyUsage = digitalSignature, keyEncipherment >> extfile.cnf ```   
  ``` echo extendedKeyUsage = serverAuth >> extfile.cnf ```

6. 使用根证书签发服务器证书   
  ``` openssl x509 -req -days 365 -sha256 -in server.csr -CA ca.pem -CAkey ca-key.pem -CAcreateserial -out server-cert.pem -extfile extfile.cnf ```

7. 创建客户端证书私钥   
  ``` openssl genrsa -out key.pem 4096 ``` 

8. 生成客户端证书签名请求   
  ``` openssl req -new -key key.pem -out client.csr ```

9. 签发客户端证书   
  ``` echo extendedKeyUsage = clientAuth > extfile-client.cnf ```   
  ``` openssl x509 -req -days 365 -sha256 -in client.csr -CA ca.pem -CAkey ca-key.pem -CAcreateserial -out cert.pem -extfile extfile-client.cnf ```

10. 收尾操作   
  ``` rm -v client.csr server.csr extfile.cnf extfile-client.cnf ```   
  ``` chmod -v 0400 ca-key.pem key.pem server-key.pem ```   
  ``` chmod -v 0444 ca.pem server-cert.pem cert.pem ```   

11. 启动 docker daemon    
  ``` dockerd --tlsverify --tlscacert=ca.pem --tlscert=server-cert.pem --tlskey=server-key.pem -H=0.0.0.0:2376 ```

12. 连接 docker daemon   
  ``` docker --tlsverify --tlscacert=ca.pem --tlscert=cert.pem --tlskey=key.pem -H=$HOST:2376 version ```