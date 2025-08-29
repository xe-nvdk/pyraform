## Vultr Resources (beta)

### Instance

```yaml
resources:
  - type: instance
    name: web-vultr
    properties:
      region: ewr
      plan: vc2-1c-1gb
      os_id: 1743
      ssh_keys: [my-key]
      tags: [web]
```



### Startup Script

```yaml
resources:
  - type: startup_script
    name: init-web
    properties:
      type: boot
      script: |
        #!/bin/bash
        echo "Hello from startup script" > /root/hello.txt
```

Instances can reference a startup script by name via `startup_script`.

### SSH Key

```yaml
resources:
  - type: ssh_key
    name: my-key
    properties:
      public_key: ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC...
```

Instances can reference SSH keys by label in `ssh_keys: [my-key]` or rely on keys already present in the account.
### Domain & DNS Record

```yaml
resources:
  - type: domain
    name: example.com
    properties:
      ip_address: 203.0.113.10

  - type: dns_record
    name: app-a
    properties:
      domain: example.com
      type: A
      name: app
      data: 203.0.113.11
      ttl: 300
```

### Block Storage (volume)

```yaml
resources:
  - type: volume
    name: data-block
    properties:
      region: ewr
      size_gb: 50
      attach_to: web-vultr
```

### Firewall

```yaml
resources:
  - type: firewall
    name: web-fw
    properties:
      rules:
        - protocol: tcp
          ip_type: v4
          subnet: 0.0.0.0
          subnet_size: 0
          port: "80"
      instances: [web-vultr]
```

### Load Balancer

```yaml
resources:
  - type: load_balancer
    name: web-lb
    properties:
      region: ewr
      forwarding_rules:
        - frontend_protocol: http
          frontend_port: 80
          backend_protocol: http
          backend_port: 80
      health_check:
        protocol: http
        port: 80
        path: /
      instances: [web-vultr]
```

### Snapshot

```yaml
resources:
  - type: snapshot
    name: web-snap-2024-06-01
    properties:
      instance: web-vultr
```

Notes:
- Requires `vultr_credentials.api_key` in `settings.yml`.
- Endpoints for block storage may vary; operations are best-effort with clear logs.

### VPC

```yaml
resources:
  - type: vpc
    name: app-vpc
    properties:
      region: ewr
      description: app network
      # optional for custom CIDR
      ip_block: 10.20.0.0
      prefix_length: 20
      instances: [web-vultr]
```

### Reserved IP

```yaml
resources:
  - type: reserved_ip
    name: web-reserved
    properties:
      region: ewr
      ip_type: v4
      attach_to: web-vultr
```

### Object Storage (S3-compatible)

```yaml
resources:
  - type: object_storage
    name: my-bucket
    properties:
      region: ewr1
```

settings.yml needs credentials under `vultr_object_storage`:

```yaml
vultr_object_storage:
  access_key: ${VULTR_OBJECT_ACCESS}
  secret_key: ${VULTR_OBJECT_SECRET}
  region: ewr1
```
