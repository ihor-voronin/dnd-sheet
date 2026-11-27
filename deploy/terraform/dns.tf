# DNS in Cloudflare: dnd.voronin.app → the server IP.
#
# The record isn't proxied by Cloudflare (the "grey cloud"): traffic goes straight to the
# server, and Let's Encrypt issues the certificate through Caddy. The provider takes the API
# token from the CLOUDFLARE_API_TOKEN environment variable (deploy.ps1 reads deploy/secrets/cloudflare.env).
provider "cloudflare" {}

data "cloudflare_zone" "site" {
  filter = {
    name = var.cloudflare_zone
  }
}

resource "cloudflare_dns_record" "site" {
  zone_id = data.cloudflare_zone.site.id
  name    = var.domain
  type    = "A"
  content = var.server_ip
  ttl     = 1
  proxied = false
  comment = "dnd-sheet: managed by Terraform (deploy/terraform)"
}
