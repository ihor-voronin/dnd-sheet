terraform {
  required_version = ">= 1.6"

  # Стан лежить поруч із доступами, поза git: у ньому хеші й адреса сервера.
  backend "local" {
    path = "../local/terraform.tfstate"
  }
}
