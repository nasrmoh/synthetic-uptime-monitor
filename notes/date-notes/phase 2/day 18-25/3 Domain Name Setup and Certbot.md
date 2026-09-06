# Domain, DNS, and TLS Setup

We purchased the domain:

```text
nasrmoha.dev
```

from the registrar **Porkbun**.

Using Porkbun's DNS management, we created an **A record** that maps the hostname:

```text
synthetic.nasrmoha.dev
```

to the public IPv4 address assigned to our Azure VM.

Conceptually:

```text
synthetic.nasrmoha.dev
        ↓ DNS A record
Azure VM public IPv4
```

## Update nginx for the Hostname

nginx also needs to know that our configuration is associated with this hostname.

We update the existing nginx configuration:

```nginx
server {
    listen 80;
    server_name synthetic.nasrmoha.dev;

    location / {
        proxy_pass http://127.0.0.1:8000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

The important addition is:

```nginx
server_name synthetic.nasrmoha.dev;
```

This tells nginx that requests for:

```text
synthetic.nasrmoha.dev
```

should be handled by this `server` block.

---

## Allow HTTP and HTTPS Through the Azure NSG

DNS and nginx configuration are not enough by themselves.

The Azure VM is protected by a Network Security Group. Our original public SSH rule was only used during bootstrap and is disabled afterward.

For the public application, we need to explicitly allow:

```text
TCP 80  → HTTP
TCP 443 → HTTPS
```

We add these rules through Terraform:

```hcl
resource "azurerm_network_security_rule" "http-security-rule" {
  name      = "http-inbound-security"
  access    = "Allow"
  priority  = 110
  direction = "Inbound"
  protocol  = "Tcp"

  resource_group_name         = azurerm_resource_group.synth-resource-group.name
  network_security_group_name = azurerm_network_security_group.synth-network-security-group.name

  source_address_prefix      = "Internet"
  source_port_range          = "*"
  destination_address_prefix = "*"
  destination_port_range     = "80"
}

resource "azurerm_network_security_rule" "https-security-rule" {
  name      = "https-inbound-security"
  access    = "Allow"
  priority  = 120
  direction = "Inbound"
  protocol  = "Tcp"

  resource_group_name         = azurerm_resource_group.synth-resource-group.name
  network_security_group_name = azurerm_network_security_group.synth-network-security-group.name

  source_address_prefix      = "Internet"
  source_port_range          = "*"
  destination_address_prefix = "*"
  destination_port_range     = "443"
}
```

After running:

```bash
terraform apply
```

the VM can receive public HTTP and HTTPS traffic through nginx.

At this stage, we can verify that DNS and HTTP routing work:

```bash
curl http://synthetic.nasrmoha.dev
```

The request path is now:

```text
synthetic.nasrmoha.dev
        ↓ DNS
Azure VM public IP
        ↓ port 80
nginx
        ↓ port 8000
FastAPI
```

---

## Obtain a TLS Certificate with Certbot

Once the domain resolves correctly and nginx is reachable publicly over port `80`, we can request a TLS certificate.

Certbot is already installed on the VM through Ansible.

On the VM, we run:

```bash
sudo certbot certonly --nginx -d synthetic.nasrmoha.dev
```

Certbot verifies that we control the domain and obtains a certificate from Let's Encrypt.

The certificate files are stored under:

```text
/etc/letsencrypt/live/synthetic.nasrmoha.dev/
```

The two files nginx needs are:

```text
fullchain.pem
privkey.pem
```

---

## Update nginx for HTTPS

We now update the nginx configuration again.

The new configuration has two `server` blocks.

The first listens on port `80` and redirects all HTTP traffic to HTTPS.

The second listens on port `443`, loads the TLS certificate, and proxies the request to FastAPI.

```nginx
server {
    listen 80;
    server_name synthetic.nasrmoha.dev;

    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name synthetic.nasrmoha.dev;

    ssl_certificate /etc/letsencrypt/live/synthetic.nasrmoha.dev/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/synthetic.nasrmoha.dev/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

The HTTP request path is now:

```text
synthetic.nasrmoha.dev
        ↓ DNS
Azure VM public IP
        ↓ port 80
nginx
        ↓
301 redirect
        ↓ port 443
nginx + TLS
        ↓ port 8000
FastAPI
```

The HTTPS path is:

```text
synthetic.nasrmoha.dev
        ↓ DNS
Azure VM public IP
        ↓ port 443
nginx + TLS
        ↓ port 8000
FastAPI
```

nginx terminates the TLS connection. The client communicates securely with nginx over HTTPS, while nginx forwards the request internally to FastAPI over HTTP.

---

## Verify the HTTP Redirect

We can confirm that HTTP requests are redirected to HTTPS:

```bash
curl -I http://synthetic.nasrmoha.dev/health
```

Output:

```text
HTTP/1.1 301 Moved Permanently
Server: nginx/1.24.0 (Ubuntu)
Date: Sun, 06 Sep 2026 10:37:34 GMT
Content-Type: text/html
Content-Length: 178
Connection: keep-alive
Location: https://synthetic.nasrmoha.dev/health
```

The important result is:

```text
HTTP/1.1 301 Moved Permanently
Location: https://synthetic.nasrmoha.dev/health
```

This confirms nginx receives the HTTP request and redirects the client to HTTPS.

---

## Verify HTTPS

We can then verify the complete HTTPS path:

```bash
curl -v https://synthetic.nasrmoha.dev/health
```

Output:

```text
* Host synthetic.nasrmoha.dev:443 was resolved.
* IPv6: (none)
* IPv4: 52.162.156.176
*   Trying 52.162.156.176:443...
* Connected to synthetic.nasrmoha.dev (52.162.156.176) port 443
* ALPN: curl offers h2,http/1.1
* TLSv1.3 (OUT), TLS handshake, Client hello (1):
*  CAfile: /etc/ssl/certs/ca-certificates.crt
*  CApath: /etc/ssl/certs
* TLSv1.3 (IN), TLS handshake, Server hello (2):
* TLSv1.3 (IN), TLS handshake, Encrypted Extensions (8):
* TLSv1.3 (IN), TLS handshake, Certificate (11):
* TLSv1.3 (IN), TLS handshake, CERT verify (15):
* TLSv1.3 (IN), TLS handshake, Finished (20):
* TLSv1.3 (OUT), TLS change cipher, Change cipher spec (1):
* TLSv1.3 (OUT), TLS handshake, Finished (20):
* SSL connection using TLSv1.3 / TLS_AES_256_GCM_SHA384 / X25519 / id-ecPublicKey
* ALPN: server accepted http/1.1
* Server certificate:
*  subject: CN=synthetic.nasrmoha.dev
*  start date: Sep  6 09:19:28 2026 GMT
*  expire date: Dec  5 09:19:27 2026 GMT
*  subjectAltName: host "synthetic.nasrmoha.dev" matched cert's "synthetic.nasrmoha.dev"
*  issuer: C=US; O=Let's Encrypt; CN=YE1
*  SSL certificate verify ok.
> GET /health HTTP/1.1
> Host: synthetic.nasrmoha.dev
> User-Agent: curl/8.5.0
> Accept: */*
< HTTP/1.1 200 OK
< Server: nginx/1.24.0 (Ubuntu)
< Date: Sun, 06 Sep 2026 10:38:32 GMT
< Content-Type: application/json
< Content-Length: 15
< Connection: keep-alive
< x-correlation-id: bdd11396-ee6d-40b0-b885-d4db316a4289
```

This verifies several things at once:

```text
DNS resolution                 ✅
Public port 443 reachable      ✅
TLS handshake succeeds         ✅
Certificate hostname matches   ✅
Certificate verification       ✅
nginx receives the request     ✅
nginx proxies to FastAPI       ✅
FastAPI returns HTTP 200       ✅
```

At this point the application is publicly reachable at:

```text
https://synthetic.nasrmoha.dev
```

through nginx with a valid Let's Encrypt TLS certificate.