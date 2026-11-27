variable "server_ip" {
  description = "The VPS IP address."
  type        = string
}

variable "ssh_user" {
  description = "The SSH user (root on RackNerd)."
  type        = string
  default     = "root"
}

variable "ssh_port" {
  description = "The SSH port."
  type        = number
  default     = 22
}

variable "ssh_private_key_path" {
  description = "The private deploy key (encrypted by git-crypt, deploy/secrets/ssh)."
  type        = string
  default     = "../secrets/ssh/id_ed25519"
}

variable "domain" {
  description = "The site domain (the Cloudflare A record points to the server; Caddy obtains the HTTPS certificate itself)."
  type        = string
}

variable "cloudflare_zone" {
  description = "The Cloudflare zone that holds the domain (e.g. voronin.app). The token is in the CLOUDFLARE_API_TOKEN variable (deploy.ps1 takes it from deploy/secrets/cloudflare.env)."
  type        = string
}

variable "disable_password_login" {
  description = "After setup, SSH sign-in is key-only (the root password no longer works)."
  type        = bool
  default     = true
}
