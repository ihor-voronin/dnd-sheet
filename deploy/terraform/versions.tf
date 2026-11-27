terraform {
  required_version = ">= 1.6"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"
    }
  }

  # Стан лежить поруч із доступами, поза git: у ньому хеші й адреса сервера.
  backend "local" {
    path = "../local/terraform.tfstate"
  }
}
