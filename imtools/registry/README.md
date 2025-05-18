### 准备 registry 运行环境

1. 执行 `./maker-certs.sh` 生成证书
2. 执行 `./make-passwd.sh` 生成 registry 帐号
3. 执行 `./setup-certs.sh` 将证书设置为可信证书
4. 设置 `registry-data` 目录(NFS)
5. 通过配置文件 `registry.yaml` 部署 registry 服务

### 镜像操作

#### 镜像拉取和推送

- 为镜像重新打上标签   
  ```docker tag busybox:latest registry.iasf/busybox```


- 推送镜像   
  ```docker push registry.iasf/busybox```


- 拉取镜像   
  ```docker pull registry.iasf/busybox```

#### 管理 registry

- 查看镜像列表   
  ```curl -u user:password http://image.dals:5000/v2/_catalog```

- 查看镜像标签列表   
  ```curl -u user:password http://image.dals:5000/v2/image-name/tags/list```

- 查看镜像清单(manifests)   
  ```curl -I -u user:password http://image.dals:5000/v2/image-name/manifests/tag-name```   
  或    
  ```curl -I -H "Accept: application/vnd.docker.distribution.manifest.v2+json" http://registry-host:5000/v2/nginx/manifests/latest ```

- 镜像删除  
  ```curl -X DELETE -u username:password https://registry-host:5000/v2/nginx/manifests/sha256:abc123```

- 镜像删除后需定期执行垃圾回收!