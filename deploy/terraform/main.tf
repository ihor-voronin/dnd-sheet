# Деплой dnd-sheet на VPS RackNerd.
#
# RackNerd не має API для Terraform, тож сам сервер Terraform не створює — він
# доводить уже наявний VPS до потрібного стану по SSH:
#   1. bootstrap — Docker, файрвол, swap, щоденний бекап бази, вхід лише ключем;
#   2. image     — образ, зібраний тут (`docker compose build app`), їде на сервер
#                  стиснутим (files/save-image.ps1);
#                  його id передає deploy.ps1 (провайдер external до Docker Desktop
#                  не достукується, а local-exec — так);
#   3. app       — compose з Caddy, .env із deploy/secrets/prod.env, запуск і перевірка /healthz.
# Кожен крок повторюється лише тоді, коли змінилося те, від чого він залежить.

locals {
  files      = "${path.module}/files"
  remote_dir = "/opt/dndsheet"

  # Файли їдуть на Linux: прибираємо \r, якщо git на Windows їх додав.
  bootstrap = replace(file("${local.files}/bootstrap.sh"), "\r\n", "\n")
  compose   = replace(file("${local.files}/compose.yml"), "\r\n", "\n")
  caddyfile = templatefile("${local.files}/Caddyfile.tftpl", {
    domain    = var.domain
    server_ip = var.server_ip
  })
  env = sensitive(replace(file(var.env_file), "\r\n", "\n"))

  image_tar = abspath("${path.module}/../local/image.tar.gz")
  site_url  = "https://${var.domain}/"
}

resource "terraform_data" "bootstrap" {
  triggers_replace = [sha256(local.bootstrap), var.disable_password_login]

  connection {
    type        = "ssh"
    host        = var.server_ip
    port        = var.ssh_port
    user        = var.ssh_user
    private_key = file(var.ssh_private_key_path)
  }

  provisioner "file" {
    content     = local.bootstrap
    destination = "/tmp/dndsheet-bootstrap.sh"
  }

  provisioner "remote-exec" {
    inline = [
      "bash /tmp/dndsheet-bootstrap.sh ${var.disable_password_login}",
      "rm -f /tmp/dndsheet-bootstrap.sh",
    ]
  }
}

resource "terraform_data" "image" {
  triggers_replace = [var.image_id]
  depends_on       = [terraform_data.bootstrap]

  # docker save + gzip: на сервер їде ~105 МБ замість ~470 МБ tar.
  provisioner "local-exec" {
    interpreter = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", abspath("${local.files}/save-image.ps1"), var.image]
    command     = local.image_tar
  }

  connection {
    type        = "ssh"
    host        = var.server_ip
    port        = var.ssh_port
    user        = var.ssh_user
    private_key = file(var.ssh_private_key_path)
  }

  provisioner "file" {
    source      = local.image_tar
    destination = "/tmp/dndsheet-image.tar.gz"
  }

  provisioner "remote-exec" {
    inline = [
      "docker load -i /tmp/dndsheet-image.tar.gz",
      "rm -f /tmp/dndsheet-image.tar.gz",
    ]
  }
}

resource "terraform_data" "app" {
  triggers_replace = [
    var.image_id,
    sha256(local.compose),
    sha256(local.caddyfile),
    sha256(local.env),
  ]
  # Запис DNS — до запуску Caddy: інакше Let's Encrypt не знайде сервер за доменом.
  depends_on = [terraform_data.image, cloudflare_dns_record.site]

  connection {
    type        = "ssh"
    host        = var.server_ip
    port        = var.ssh_port
    user        = var.ssh_user
    private_key = file(var.ssh_private_key_path)
  }

  provisioner "file" {
    content     = local.compose
    destination = "${local.remote_dir}/compose.yml"
  }

  provisioner "file" {
    content     = local.caddyfile
    destination = "${local.remote_dir}/Caddyfile"
  }

  provisioner "file" {
    content     = local.env
    destination = "${local.remote_dir}/.env"
  }

  provisioner "remote-exec" {
    inline = [
      "chmod 600 ${local.remote_dir}/.env",
      "cd ${local.remote_dir} && DNDSHEET_IMAGE=${var.image} docker compose -f compose.yml up -d --remove-orphans",
      "docker image prune -f",
      # Застосунок мусить стати healthy (HEALTHCHECK образу); інакше — журнал і помилка.
      "for i in $(seq 1 45); do [ \"$(docker inspect -f '{{.State.Health.Status}}' dndsheet-app)\" = healthy ] && echo 'app: healthy' && break; sleep 2; done; [ \"$(docker inspect -f '{{.State.Health.Status}}' dndsheet-app)\" = healthy ] || { cd ${local.remote_dir} && docker compose -f compose.yml logs --tail 60 app; exit 1; }",
      # HTTPS через Caddy: перший сертифікат може зайняти хвилину — тут лише попередження.
      "for i in $(seq 1 30); do curl -fsS --resolve ${var.domain}:443:127.0.0.1 https://${var.domain}/healthz >/dev/null 2>&1 && echo 'https: OK' && exit 0; sleep 3; done; echo 'https: ще немає сертифіката — дивіться docker logs dndsheet-caddy'; docker logs --tail 30 dndsheet-caddy",
    ]
  }
}
