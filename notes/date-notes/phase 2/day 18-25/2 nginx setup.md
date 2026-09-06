# nginx Setup

Setting up nginx is a little different from configuring something like Docker Compose because nginx runs as a service on the VM and reads its configuration from specific locations on the filesystem.

For our deployment, nginx will act as the public HTTP entry point and forward requests to the FastAPI application running on port `8000`.

## Create the nginx Configuration

We first create the nginx configuration file inside the project:

```text
deploy/synthetic-uptime-monitor.conf
```

The configuration is:

```nginx
server {
    listen 80;

    location / {
        proxy_pass http://127.0.0.1:8000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

This tells nginx to:

```text
listen for HTTP requests on port 80
        ↓
match requests under /
        ↓
forward them to FastAPI on port 8000
```

The forwarded headers preserve information about the original request, such as the requested host, client IP, and protocol.

## Deploy the Configuration with Ansible

The configuration file exists inside our repository, but nginx on the VM expects site-specific configuration under:

```text
/etc/nginx/sites-available/
```

We therefore use Ansible to copy the file into the correct location.

nginx also loads enabled sites through:

```text
/etc/nginx/sites-enabled/
```

Rather than creating a second copy of the configuration file, we create a symbolic link:

```text
/etc/nginx/sites-enabled/synthetic-uptime-monitor.conf
        ↓
/etc/nginx/sites-available/synthetic-uptime-monitor.conf
```

We also remove Ubuntu's default nginx site so that our application configuration handles incoming requests.

Finally, nginx is reloaded so that it begins using the new configuration.

```yaml
- name: Setup nginx
  become: true
  hosts: synth-vm

  tasks:
    - name: Copy in the Configuration file
      ansible.builtin.copy:
        src: "{{ playbook_dir }}/../deploy/synthetic-uptime-monitor.conf"
        dest: /etc/nginx/sites-available/synthetic-uptime-monitor.conf
        owner: root
        group: root
        mode: '0644'

    - name: Create a symbolic link from available to enabled
      ansible.builtin.file:
        src: /etc/nginx/sites-available/synthetic-uptime-monitor.conf
        dest: /etc/nginx/sites-enabled/synthetic-uptime-monitor.conf
        state: link

    - name: Remove default config file
      ansible.builtin.file:
        path: /etc/nginx/sites-enabled/default
        state: absent

    - name: Reload nginx
      ansible.builtin.command:
        cmd: systemctl reload nginx
      changed_when: false
```

Before reloading nginx manually, we can also validate the configuration with:

```bash
sudo nginx -t
```

A successful result confirms that nginx can parse the active configuration.

## Accessing the Application

Once the Ansible playbook has been run and nginx has loaded the configuration, we can access the application through the VM's Tailscale address without specifying port `8000`.

For example:

```text
http://<vm-private-tailscale-ip>/ready
http://<vm-private-tailscale-ip>/health
http://<vm-private-tailscale-ip>/docs
```

Because HTTP uses port `80` by default, the client connects to nginx.

nginx then creates a separate request to FastAPI on port `8000`, receives FastAPI's response, and returns that response to the client.

The request path is now:

```text
Client
  ↓ port 80
nginx
  ↓ port 8000
FastAPI
```

rather than:

```text
Client
  ↓ port 8000
FastAPI
```

Port `8000` can still be reached directly over our private Tailscale network for debugging, but normal HTTP traffic can now go through nginx on port `80`.