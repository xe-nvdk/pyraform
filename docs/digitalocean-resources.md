## DigitalOcean Resources

This page lists well‑formed YAML examples for all supported DigitalOcean resource types.

### Droplet

```yaml
resources:
  - type: droplet
    name: web-server
    properties:
      image: ubuntu-20-04-x64
      size: s-1vcpu-1gb
      region: nyc3
      ssh_keys: [m1]
      backups: true
      tags: [web, app]
      # Optional update controls
      allow_power_cycle_for_resize: true  # permit power off/on if resize requires it
      delete_unused_tags: true            # delete tag objects after detaching
```

### Volume

```yaml
resources:
  - type: volume
    name: data-disk
    properties:
      size_gigabytes: 25
      region: nyc3
      description: app data
      attach_to: web-server
```

### Domain

```yaml
resources:
  - type: domain
    name: root-domain
    properties:
      name: example.com
      ip_address: 203.0.113.10
```

### DNS Record

```yaml
resources:
  - type: dns_record
    name: app-a-record
    properties:
      domain: example.com
      type: A
      name: app
      data: 203.0.113.11
      ttl: 1800
```

### Firewall

```yaml
resources:
  - type: firewall
    name: web-fw
    properties:
      inbound_rules:
        - protocol: tcp
          ports: "80"
          sources: {addresses: ["0.0.0.0/0", "::/0"]}
      outbound_rules:
        - protocol: tcp
          ports: "all"
          destinations: {addresses: ["0.0.0.0/0", "::/0"]}
      droplets: [web-server]
      tags: [web]
```

### Load Balancer

```yaml
resources:
  - type: load_balancer
    name: web-lb
    properties:
      region: nyc3
      forwarding_rules:
        - entry_protocol: http
          entry_port: 80
          target_protocol: http
          target_port: 80
      health_check:
        protocol: http
        port: 80
        path: /
      droplets: [web-server]
```

### Floating IP

```yaml
resources:
  - type: floating_ip
    name: public-ip
    properties:
      region: nyc3
      assign_to: web-server
```

### Space (DO Spaces / S3 compatible)

```yaml
resources:
  - type: space
    name: my-space
    properties:
      region: nyc3
      acl: private
      force_destroy: true   # also clears versioned objects
      versioning: true
      lifecycle:
        Rules:
          - ID: expire-old-versions
            Status: Enabled
            NoncurrentVersionExpiration:
              NoncurrentDays: 30
```

### VPC

```yaml
resources:
  - type: vpc
    name: app-vpc
    properties:
      region: nyc3
      ip_range: 10.10.0.0/20
      description: app network
```

### Kubernetes

```yaml
resources:
  - type: kubernetes
    name: app-cluster
    properties:
      region: nyc1
      version: 1.29.1-do.0
      node_pools:
        - name: pool-1
          size: s-2vcpu-4gb
          count: 2
      tags: [prod]
```

### Database (Managed)

```yaml
resources:
  - type: database
    name: app-db
    properties:
      engine: pg
      version: 15
      size: db-s-1vcpu-1gb
      region: nyc3
      num_nodes: 1
```

Notes:
- Names in fields like `attach_to`, `droplets`, and `assign_to` refer to resource names in the same config and are resolved to IDs automatically.
- Some operations depend on API/library support (e.g., volume resize, k8s/database classes). The tool logs clearly if unsupported.

