terraform {
  required_version = ">= 1.6"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"
    }
  }

  # Стан у git, але зашифрований git-crypt (deploy/secrets/**): його бачить
  # кожен, хто розблокував репозиторій, і ніхто в GitHub.
  backend "local" {
    path = "../secrets/terraform/terraform.tfstate"
  }
}
