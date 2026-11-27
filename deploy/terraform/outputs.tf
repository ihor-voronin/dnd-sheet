output "site_url" {
  description = "The site URL."
  value       = local.site_url
}

output "ssh" {
  description = "Log in to the server with the deploy key."
  value       = "ssh -i ${var.ssh_private_key_path} -p ${var.ssh_port} ${var.ssh_user}@${var.server_ip}"
}
