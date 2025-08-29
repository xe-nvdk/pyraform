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

Notes:
- Requires `vultr_credentials.api_key` in `settings.yml`.
- Endpoints for block storage may vary; operations are best-effort with clear logs.

