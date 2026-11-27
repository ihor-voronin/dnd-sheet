terraform {
  required_version = ">= 1.6"

  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 5.0"
    }
  }

  # The state is in git, but encrypted by git-crypt (deploy/secrets/**): anyone who
  # unlocked the repository can see it, and nobody on GitHub can.
  backend "local" {
    path = "../secrets/terraform/terraform.tfstate"
  }
}
