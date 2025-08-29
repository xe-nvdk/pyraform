# Pyraform

![Pyraform](<pyraform.webp>)

Pyraform is a Python-based, multi‑cloud IaC tool. Define infrastructure in simple YAML, plan the changes, and apply them consistently. DigitalOcean is the most complete provider today; AWS, GCP, Vultr and others are planned.

## Features

- **Infrastructure as Code**: Simple YAML to describe resources and relationships.
- **Plan & Apply**: Preview diffs per resource before applying.
- **State Management**: Tracks current resources in `state.json` with upsert behavior.
- **DigitalOcean‑first**: Droplets, Volumes, Firewalls, Load Balancers, Floating IPs, VPCs, Domains, DNS, Kubernetes, Databases, Spaces.
- **Extensible**: AWS integration exists; more providers incoming. Contributions welcome.

## Getting Started

To use Pyraform, clone this repository and install the required dependencies:

```bash
git clone https://github.com/xe-nvdk/pyraform.git
cd pyraform
pip install -r requirements.txt
```

## Configuration
Define your infrastructure in a YAML file (e.g., infrastructure.yml). Here's an example to get you started:

```yaml
resources:
  - type: droplet
    name: web-server
    properties:
      image: ubuntu-20-04-x64  # Example image slug for Ubuntu 20.04
      size: s-1vcpu-1gb        # Example droplet size, similar to t2.micro
      ssh_keys: [m1]           # You would specify the SSH key ID or fingerprint
      region: nyc3             # New York 3 datacenter
      user_data: "./webserver.sh"  # Path to a script to run on instance creation
      tags:
        - web
        - production
```

## Deploying a DigitalOcean Droplet
You can pass custom config paths via flags, or rely on defaults (`settings.yml` and `infrastructure.yml` in the CWD). For the example below, point to the sample files:

```bash
python3 pyraform.py plan \
  --settings examples/digitalocean/droplet-deployment/settings.yml \
  --infrastructure examples/digitalocean/droplet-deployment/infrastructure.yml

python3 pyraform.py deploy \
  --settings examples/digitalocean/droplet-deployment/settings.yml \
  --infrastructure examples/digitalocean/droplet-deployment/infrastructure.yml \
  --provider do \
  --auto-approve \
  --verbose
```

The planner prints a table of actions and a summary such as: `Plan: 1 to add, 0 to change, 0 unchanged.`

## Destroying DigitalOcean Droplet
To tear down your infrastructure, use the same flags if using example files:

```bash
python3 pyraform.py destroy \
  --settings examples/digitalocean/droplet-deployment/settings.yml \
  --infrastructure examples/digitalocean/droplet-deployment/infrastructure.yml
```

## DigitalOcean Resources

Below are example snippets you can include in your `infrastructure.yml` to manage more DigitalOcean resources.

- droplet
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
      allow_power_cycle_for_resize: true  # permit power-off/on if resize requires it
      delete_unused_tags: true            # drop tags from account when not desired
      
- volume
  - type: volume
    name: data-disk
    properties:
      size_gigabytes: 10
      region: nyc3
      description: app data
      attach_to: web-server

- domain
  - type: domain
    name: root-domain
    properties:
      name: example.com
      ip_address: 203.0.113.10

- dns_record
  - type: dns_record
    name: app-a-record
    properties:
      domain: example.com
      type: A
      name: app
      data: 203.0.113.11
      ttl: 1800

- firewall
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

- load_balancer
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

- floating_ip
  - type: floating_ip
    name: public-ip
    properties:
      region: nyc3
      assign_to: web-server

- space
  - type: space
    name: my-space
    properties:
      region: nyc3
      acl: private
      force_destroy: true
      # force_destroy also clears versioned objects
      versioning: true
      lifecycle:
        Rules:
          - ID: expire-old-versions
            Status: Enabled
            NoncurrentVersionExpiration:
              NoncurrentDays: 30

- vpc
  - type: vpc
    name: app-vpc
    properties:
      region: nyc3
      ip_range: 10.10.0.0/20
      description: app network

- kubernetes
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

- database
  - type: database
    name: app-db
    properties:
      engine: pg
      version: 15
      size: db-s-1vcpu-1gb
      region: nyc3
      num_nodes: 1

Notes:
- Names in fields like `attach_to`, `droplets`, and `assign_to` refer to resource names in the same config and are resolved to IDs automatically.
- Use `--verbose` to see detailed logs and `--auto-approve` to bypass interactive prompts.
- Kubernetes and Database support requires a python-digitalocean version that provides these classes; otherwise, the tool logs a clear message.

### CLI Flags
- `--settings`: Path to `settings.yml` (defaults to `./settings.yml`).
- `--infrastructure`: Path to `infrastructure.yml` (defaults to `./infrastructure.yml`).
- `--provider`: Provider override, e.g. `do`.
- `--auto-approve`: Skips interactive confirmation.
- `--verbose`: Enables detailed logs.

## Examples

Kubernetes cluster:

```bash
python3 pyraform.py plan \
  --settings examples/digitalocean/k8s-cluster/settings.yml \
  --infrastructure examples/digitalocean/k8s-cluster/infrastructure.yml \
  --provider do

python3 pyraform.py deploy \
  --settings examples/digitalocean/k8s-cluster/settings.yml \
  --infrastructure examples/digitalocean/k8s-cluster/infrastructure.yml \
  --provider do --auto-approve
```

Database cluster:

```bash
python3 pyraform.py plan \
  --settings examples/digitalocean/database-cluster/settings.yml \
  --infrastructure examples/digitalocean/database-cluster/infrastructure.yml \
  --provider do

python3 pyraform.py deploy \
  --settings examples/digitalocean/database-cluster/settings.yml \
  --infrastructure examples/digitalocean/database-cluster/infrastructure.yml \
  --provider do --auto-approve
```

Other resources:

```bash
# Firewall
python3 pyraform.py plan \
  --settings examples/digitalocean/firewall/settings.yml \
  --infrastructure examples/digitalocean/firewall/infrastructure.yml --provider do

# Load Balancer
python3 pyraform.py plan \
  --settings examples/digitalocean/load-balancer/settings.yml \
  --infrastructure examples/digitalocean/load-balancer/infrastructure.yml --provider do

# Floating IP
python3 pyraform.py plan \
  --settings examples/digitalocean/floating-ip/settings.yml \
  --infrastructure examples/digitalocean/floating-ip/infrastructure.yml --provider do

# VPC
python3 pyraform.py plan \
  --settings examples/digitalocean/vpc/settings.yml \
  --infrastructure examples/digitalocean/vpc/infrastructure.yml --provider do
```

All-in-one:

```bash
python3 pyraform.py plan \
  --settings examples/digitalocean/all-in-one/settings.yml \
  --infrastructure examples/digitalocean/all-in-one/infrastructure.yml --provider do

python3 pyraform.py deploy \
  --settings examples/digitalocean/all-in-one/settings.yml \
  --infrastructure examples/digitalocean/all-in-one/infrastructure.yml --provider do --auto-approve
```

Destroy all-in-one:

```bash
python3 pyraform.py destroy \
  --settings examples/digitalocean/all-in-one/settings.yml \
  --infrastructure examples/digitalocean/all-in-one/infrastructure.yml --provider do --auto-approve
```

Destroy planning view:

```bash
python3 pyraform.py destroy \
  --settings examples/digitalocean/droplet-deployment/settings.yml \
  --infrastructure examples/digitalocean/droplet-deployment/infrastructure.yml \
  --provider do
# Shows only resources to destroy based on current state
```

## Contributing
Contributions to Pyraform are welcome! Please refer to the CONTRIBUTING.md file for guidelines.

## License
This project is licensed under the MIT License - see the LICENSE file for details.
