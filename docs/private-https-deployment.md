# Private HTTPS deployment on Oracle Cloud

This deployment serves `https://reviews.openjack.xyz` only over Tailscale. Cloudflare is
the authoritative DNS provider and Certbot uses its API for DNS-01 certificate
validation, but Cloudflare does **not** proxy application traffic.

## Traffic design

```text
Tailscale client -> reviews.openjack.xyz -> 100.116.133.57 -> Nginx :443 -> app containers
Public client    -> reviews.openjack.xyz -> 100.116.133.57 -> no route
```

Nginx binds ports 80 and 443 only on the Oracle server's Tailscale address. It
also rejects source addresses outside Tailscale's `100.64.0.0/10` range. The
frontend, API, and PostgreSQL services are not published by the production
Compose configuration.

Do not enable Cloudflare's orange-cloud proxy for this hostname. A proxied
record sends clients to Cloudflare's public edge and changes the security model.
Do not point the record at the Oracle public IP (`132.145.208.27`).
Do not add public OCI Security List or Network Security Group ingress rules for
ports 80, 443, 5173, 8000, or 5432; remove them if they already exist. Tailscale
only needs its normal outbound connectivity (and optionally its UDP transport
port), not public web ingress.

## 1. Configure Cloudflare DNS

In Cloudflare **DNS > Records**, create this record:

| Type | Name | Content | Proxy status | TTL |
| --- | --- | --- | --- | --- |
| A | `reviews` | `100.116.133.57` | **DNS only** (gray cloud) | Auto |

Remove any other A or AAAA record for `reviews.openjack.xyz` that points at a public IP.
The Tailscale address can appear in public DNS without making it publicly
routable. If a client resolver blocks answers in the `100.64.0.0/10` range as
DNS rebinding protection, configure that Tailscale client to use a public
resolver or use Tailscale split DNS with an internal resolver.

## 2. Create a narrow Cloudflare token

In Cloudflare **My Profile > API Tokens**, create a custom token with only:

- Permission: `Zone` / `DNS` / `Edit`
- Zone resource: `Include` / `Specific zone` / `openjack.xyz`

Do not use the Global API Key. On the Oracle server, store the token outside the
repository:

```bash
sudo install -d -m 700 /etc/real-reviews
sudoedit /etc/real-reviews/cloudflare.ini
sudo chmod 600 /etc/real-reviews/cloudflare.ini
```

The file must contain exactly this setting with the real token substituted:

```ini
dns_cloudflare_api_token = YOUR_RESTRICTED_TOKEN
```

## 3. Configure and start the stack

Add these values to the repository's `.env` file:

```dotenv
APP_DOMAIN=reviews.openjack.xyz
TAILSCALE_IP=100.116.133.57
ACME_EMAIL=jackye315@gmail.com
CLOUDFLARE_CREDENTIALS_FILE=/etc/real-reviews/cloudflare.ini
```

The production Compose configuration sets the API's allowed frontend origin to
`https://reviews.openjack.xyz`; the development origin in `.env` can remain unchanged.

Then issue the certificate and start production:

```bash
make config-prod
make up-prod
make ps-prod
```

`make up-prod` uses Certbot's Cloudflare DNS-01 plugin before starting Nginx.
The renewal container checks twice a day, and Nginx reloads periodically to pick
up renewed certificates. Certificate state is stored in the `letsencrypt` Docker
volume.

Verify from a device connected to the tailnet:

```bash
curl -I https://reviews.openjack.xyz
```

Then disconnect Tailscale and repeat the request. It should time out or report no
route; it must never return the application.

## 4. Restrict the tailnet policy

Binding to the Tailscale interface prevents public access. For least privilege,
also tag this Oracle machine `tag:real-reviews` and add a Tailscale grant. Merge
these entries into the existing tailnet policy rather than replacing it:

```json
{
  "tagOwners": {
    "tag:real-reviews": ["autogroup:admin"]
  },
  "grants": [
    {
      "src": ["autogroup:member"],
      "dst": ["tag:real-reviews"],
      "ip": ["tcp:80", "tcp:443"]
    }
  ]
}
```

Use a named Tailscale group instead of `autogroup:member` if only some tailnet
members should have access. Existing broad allow-all grants remain additive and
must be removed if this rule is intended to enforce a tighter boundary.

## Operational commands

```bash
make logs-prod
make ps-prod
make cert-prod
make check-prod
make down-prod
```

`make check-prod` exits non-zero if a required container is stopped/unhealthy,
Tailscale is disconnected, the certificate expires within 14 days, or host disk
usage reaches 85%. Run it from an external scheduler or monitoring service that
alerts on non-zero exit. The Certbot renewal container also becomes unhealthy if
it cannot complete a successful renewal check for more than 25 hours.

## Backups

The PostgreSQL Docker volume is persistence, not a backup. Before treating this
as a durable production system, configure encrypted off-host `pg_dump` backups
with retention and restore tests. This repository does not select a destination
because none is configured on the server; choose an object-storage/restic target
and keep its credentials outside the repository.

Development ports bind to `TAILSCALE_IP` when it is set and otherwise bind to
`127.0.0.1`; they no longer listen on every host interface by default.
