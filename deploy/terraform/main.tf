# Інфраструктура dnd-sheet на VPS RackNerd (запускається вручну й рідко).
#
# RackNerd не має API для Terraform, тож сам сервер Terraform не створює — він
# доводить уже наявний VPS до потрібного стану по SSH:
#   1. bootstrap — Docker, файрвол, swap, щоденний бекап бази, вхід лише ключем;
#   2. dns.tf    — запис A домену в Cloudflare.
#
# Застосунок (образ, compose, Caddyfile, .env) деплоїть scripts/deploy_app.py —
# з цього компʼютера або з GitHub Actions після злиття в main. Колись це теж був
# Terraform, але тоді CI мусив би комітити стан назад у захищену гілку.

locals {
  # Скрипт їде на Linux: прибираємо \r, якщо git на Windows його додав.
  bootstrap = replace(file("${path.module}/files/bootstrap.sh"), "\r\n", "\n")
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
