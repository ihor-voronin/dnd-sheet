variable "server_ip" {
  description = "IP-адреса VPS."
  type        = string
}

variable "ssh_user" {
  description = "Користувач SSH (на RackNerd — root)."
  type        = string
  default     = "root"
}

variable "ssh_port" {
  description = "Порт SSH."
  type        = number
  default     = 22
}

variable "ssh_private_key_path" {
  description = "Приватний ключ для деплою (зашифрований git-crypt, deploy/secrets/ssh)."
  type        = string
  default     = "../secrets/ssh/id_ed25519"
}

variable "domain" {
  description = "Адреса сайту (запис A в Cloudflare веде на сервер; Caddy сам отримує сертифікат HTTPS)."
  type        = string
}

variable "cloudflare_zone" {
  description = "Зона в Cloudflare, де живе домен (напр. voronin.app). Токен — у змінній CLOUDFLARE_API_TOKEN (deploy.ps1 бере її з deploy/secrets/cloudflare.env)."
  type        = string
}

variable "disable_password_login" {
  description = "Після налаштування вхід по SSH лише ключем (пароль root більше не пускає)."
  type        = bool
  default     = true
}
