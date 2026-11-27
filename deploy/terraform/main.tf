# dnd-sheet infrastructure on a RackNerd VPS (run by hand and rarely).
#
# RackNerd has no API for Terraform, so Terraform doesn't create the server itself — it
# brings the existing VPS to the desired state over SSH:
#   1. bootstrap — Docker, firewall, swap, a daily database backup, key-only sign-in;
#   2. dns.tf    — the domain's A record in Cloudflare.
#
# The app (image, compose, Caddyfile, .env) is deployed by scripts/deploy_app.py —
# from this computer or from GitHub Actions after a merge into main. It used to be
# Terraform too, but then CI would have to commit the state back into a protected branch.

locals {
  # The script runs on Linux: strip \r in case git on Windows added it.
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
