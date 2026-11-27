# Деплой dnd-sheet на VPS RackNerd.
#
# RackNerd не має API для Terraform, тож сам сервер Terraform не створює — він
# доводить уже наявний VPS до потрібного стану по SSH:
#   1. bootstrap — Docker, файрвол, swap, щоденний бекап бази, вхід лише ключем;
#   2. image     — образ, зібраний тут (`docker compose build app`), їде на сервер;
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
    site_address = var.domain != "" ? var.domain : ":80"
  })
  env = sensitive(replace(file(var.env_file), "\r\n", "\n"))

  image_tar = abspath("${path.module}/../local/image.tar")
  site_url  = var.domain != "" ? "https://${var.domain}/" : "http://${var.server_ip}/"
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

  provisioner "local-exec" {
    command = "docker save -o \"${local.image_tar}\" ${var.image}"
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
    destination = "/tmp/dndsheet-image.tar"
  }

  provisioner "remote-exec" {
    inline = [
      "docker load -i /tmp/dndsheet-image.tar",
      "rm -f /tmp/dndsheet-image.tar",
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
  depends_on = [terraform_data.image]

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
      # Сайт мусить відповісти через Caddy; інакше — показати журнал і впасти.
      "for i in $(seq 1 45); do curl -fsS http://127.0.0.1/healthz >/dev/null 2>&1 && echo 'healthz: OK' && exit 0; sleep 2; done; cd ${local.remote_dir} && docker compose -f compose.yml logs --tail 60 app caddy; exit 1",
    ]
  }
}
