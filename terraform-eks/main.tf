terraform {
  required_version = ">= 1.12.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    helm = {
      source  = "hashicorp/helm",
      version = "~> 3.0"
    }
    local = {
      source  = "hashicorp/local",
      version = "2.5.3"
    }
  }
}

########################################
# Providers
########################################
provider "aws" {
  region = var.aws_region
}

provider "helm" {
  kubernetes = {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    token                  = data.aws_eks_cluster_auth.this.token
  }
}

provider "local" {}

########################################
# Datum and Locals
########################################

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

data "aws_eks_cluster_auth" "this" {
  name = module.eks.cluster_name
}

locals {
  root_user_arn = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"

  azs          = slice(data.aws_availability_zones.available.names, 0, 2)
  vpc_cidr     = "10.0.0.0/16"
  priv_subnets = ["10.0.0.0/24", "10.0.2.0/24"]
  pub_subnets  = ["10.0.1.0/24", "10.0.3.0/24"]
  tags = {
    "terraform"     = "true"
    "project.owner" = "humbertofraga"
    "project.name"  = "csa"
  }
}

########################################
# VPC (private subnets for worker nodes)
########################################
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  name = "${var.cluster_name}-vpc"
  cidr = local.vpc_cidr

  azs             = local.azs
  private_subnets = local.priv_subnets
  public_subnets  = local.pub_subnets

  enable_dns_hostnames   = true
  enable_dns_support     = true
  enable_nat_gateway     = true
  single_nat_gateway     = true
  one_nat_gateway_per_az = false

  tags = local.tags
}

########################################
# EKS Cluster & Managed Node Groups
########################################
module "eks" {
  source = "terraform-aws-modules/eks/aws"

  name               = var.cluster_name
  kubernetes_version = "1.33"
  upgrade_policy = {
    support_type = "STANDARD"
  }

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = [module.vpc.private_subnets[0]]
  control_plane_subnet_ids = module.vpc.private_subnets

  endpoint_public_access       = true
  endpoint_public_access_cidrs = var.allowed_cidrs
  endpoint_private_access      = true

  addons = {
    eks-pod-identity-agent = {
      before_compute = true
    }
    vpc-cni = {
      before_compute = true
    }
    coredns    = {}
    kube-proxy = {}
  }

  authentication_mode                      = "API_AND_CONFIG_MAP"
  enable_cluster_creator_admin_permissions = true

  access_entries = {
    root = {
      principal_arn = local.root_user_arn
      policy_associations = {
        eks_cluster_admin = {
          policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = {
            type = "cluster"
          }
        }
      }
    }
  }

  # Managed node groups matching requested capacities
  eks_managed_node_groups = {
    # # 2 × 2 CPU / 2 GiB
    app = {
      name           = "ng-app"
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = ["t3.small"]
      capacity_type  = "ON_DEMAND"
      desired_size   = 2
      max_size       = 2
      min_size       = 2
      labels = {
        "workload" = "app"
      }
      tags = local.tags
    }

    # # 1 × 2 CPU / 2 GiB
    db = {
      name           = "ng-db"
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = ["t3.small"]
      capacity_type  = "ON_DEMAND"
      desired_size   = 1
      max_size       = 1
      min_size       = 1
      labels = {
        "workload" = "db"
      }
      tags = local.tags
    }

    # # 1 × 2 CPU / 4 GiB
    adaptation = {
      name           = "ng-adaptation"
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = ["t3.small"]
      capacity_type  = "ON_DEMAND"
      desired_size   = 1
      max_size       = 1
      min_size       = 1
      labels = {
        "workload" = "adaptation"
      }
      tags = local.tags
    }
  }

  node_security_group_additional_rules = {
    allow_http_from_k6 = {
      description              = "Allow HTTP from k6 EC2 SG to worker nodes"
      protocol                 = "tcp"
      from_port                = 80
      to_port                  = 8080
      type                     = "ingress"
      source_security_group_id = module.ec2_k6.security_group_id
    }
  }

  tags = local.tags
}

resource "local_file" "kubeconfig" {
  filename = "${path.module}/kubeconfig_${var.cluster_name}.yaml"
  content  = <<EOT
apiVersion: v1
clusters:
- cluster:
    server: ${module.eks.cluster_endpoint}
    certificate-authority-data: ${module.eks.cluster_certificate_authority_data}
  name: ${module.eks.cluster_name}
contexts:
- context:
    cluster: ${module.eks.cluster_name}
    user: ${module.eks.cluster_name}
  name: ${module.eks.cluster_name}
current-context: ${module.eks.cluster_name}
kind: Config
preferences: {}
users:
- name: ${module.eks.cluster_name}
  user:
    token: ${data.aws_eks_cluster_auth.this.token}
EOT
}

########################################
# ECR Private Repositories
########################################

resource "aws_ecr_repository" "znn" {
  name                 = "${var.cluster_name}/znn"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

########################################
# Variables
########################################
variable "aws_region" {
  description = "AWS region to deploy the cluster"
  type        = string
  default     = "sa-east-1"
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "lab-csa"
}

variable "allowed_cidrs" {
  type    = list(string)
  default = ["179.67.254.87/32"]
}

variable "role_name" {
  type    = string
  default = "eks-tf"
}
