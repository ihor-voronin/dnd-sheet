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
  description = "Приватний ключ для деплою (лише локально, deploy/local/ssh)."
  type        = string
  default     = "../local/ssh/id_ed25519"
}

variable "image" {
  description = "Локальний Docker-образ застосунку: збирається тут, бо корпус довідника не в git."
  type        = string
  default     = "dndsheet:local"
}

variable "image_id" {
  description = "Id локального образу (`docker image inspect`): новий id — образ знову їде на сервер. Передає deploy.ps1."
  type        = string

  validation {
    condition     = startswith(var.image_id, "sha256:")
    error_message = "Запускайте через deploy.ps1 — він збирає образ і передає його id."
  }
}

variable "env_file" {
  description = "Змінні застосунку для продакшну — зашифрований git-crypt файл (має бути розблокований)."
  type        = string
  default     = "../secrets/prod.env"
}

variable "domain" {
  description = "Адреса сайту (запис A в Cloudflare веде на сервер; Caddy сам отримує сертифікат HTTPS)."
  type        = string
}

variable "cloudflare_zone" {
  description = "Зона в Cloudflare, де живе домен (напр. voronin.app). Токен — у змінній CLOUDFLARE_API_TOKEN (deploy.ps1 бере її з deploy/local/cloudflare.env)."
  type        = string
}

variable "disable_password_login" {
  description = "Після налаштування вхід по SSH лише ключем (пароль root більше не пускає)."
  type        = bool
  default     = true
}
