output "site_url" {
  description = "Адреса сайту."
  value       = local.site_url
}

output "ssh" {
  description = "Зайти на сервер ключем деплою."
  value       = "ssh -i ${var.ssh_private_key_path} -p ${var.ssh_port} ${var.ssh_user}@${var.server_ip}"
}
