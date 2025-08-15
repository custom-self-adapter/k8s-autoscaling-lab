terraform {
  required_version = ">= 1.12.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

########################################
# Provider
########################################
provider "aws" {
  region = var.aws_region
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

locals {
  root_user_arn = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"
  azs           = slice(data.aws_availability_zones.available.names, 0, 2)
  vpc_cidr      = "10.0.0.0/16"
  priv_subnets  = ["10.0.0.0/24", "10.0.1.0/24", "10.0.2.0/24"]
  pub_subnets   = ["10.0.3.0/24", "10.0.4.0/24", "10.0.5.0/24"]
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

  map_public_ip_on_launch = true
  enable_dns_hostnames    = true
  enable_dns_support      = true
  enable_nat_gateway      = true
  single_nat_gateway      = true
  create_igw              = true

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

  endpoint_public_access       = true
  endpoint_public_access_cidrs = var.allowed_cidrs
  endpoint_private_access      = true

  addons = {
    coredns = {}
    eks-pod-identity-agent = {
      before_compute = true
    }
    kube-proxy = {}
    vpc-cni = {
      before_compute = true
    }
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

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.public_subnets

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
      labels         = { "role" = "app" }
      tags           = local.tags
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
      labels         = { "role" = "db" }
      tags           = local.tags
    }

    # 1 × 2 CPU / 4 GiB
    monitor = {
      name           = "ng-monitor"
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = ["t3.medium"]
      capacity_type  = "ON_DEMAND"
      desired_size   = 1
      max_size       = 1
      min_size       = 1
      labels         = { "role" = "monitor" }
      tags           = local.tags
    }

    # # 1 × 2 CPU / 4 GiB
    adaptation = {
      name           = "ng-adaptation"
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = ["t3.medium"]
      capacity_type  = "ON_DEMAND"
      desired_size   = 1
      max_size       = 1
      min_size       = 1
      labels         = { "role" = "adaptation" }
      tags           = local.tags
    }
  }

  tags = local.tags
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
