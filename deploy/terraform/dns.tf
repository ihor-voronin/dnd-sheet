# DNS у Cloudflare: dnd.voronin.app → IP сервера.
#
# Запис без проксі Cloudflare («сіра хмарка»): трафік іде прямо на сервер, а
# сертифікат видає Let's Encrypt через Caddy. Токен API провайдер бере зі
# змінної середовища CLOUDFLARE_API_TOKEN (deploy.ps1 читає deploy/local/cloudflare.env).
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
  comment = "dnd-sheet: керує Terraform (deploy/terraform)"
}
