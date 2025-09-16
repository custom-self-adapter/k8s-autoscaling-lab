terraform {
  required_version = ">= 1.12.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    local = {
      source  = "hashicorp/local",
      version = "2.5"
    }
  }
}

########################################
# Providers
########################################
provider "aws" {
  region = var.aws_region
}

########################################
# Locals and Variables
########################################

locals {
  priv_subnets = ["10.0.0.0/24", "10.0.2.0/24"]
  pub_subnets  = ["10.0.1.0/24", "10.0.3.0/24"]

  tags = {
    "terraform"     = "true"
    "project.owner" = "humbertofraga"
    "project.name"  = "csa"
  }

  node_pools = {
    app = {
      instance_type = "t3a.medium"
      node_labels   = { "workload" = "app" }
    }
    db = {
      instance_type = "t3a.small"
      node_labels   = { "workload" = "db" }
    }
    adaptation = {
      instance_type = "t3a.small"
      node_labels   = { "workload" = "adaptation", "edge" = "ingress" }
    }
    monitoring = {
      instance_type = "t3a.small"
      node_labels   = { "workload" = "monitoring" }
    }
  }
}

variable "aws_region" {
  type    = string
  default = "sa-east-1"
}

variable "cluster_name" {
  type    = string
  default = "lab-csa"
}

variable "kubeadm_token" {
  type    = string
  default = "Wakyb+YQKt2RmcBB0K0aSvFUqHSOYbtVCFVED9VIH8Y="
}

variable "allowed_cidrs" {
  type    = list(string)
  default = ["179.67.254.87/32"]
}

variable "role_name" {
  type    = string
  default = "eks-tf"
}

########################################
# VPC (private subnets for worker nodes)
########################################
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  name = "${var.cluster_name}-vpc"
  cidr = "10.0.0.0/16"

  azs                     = ["${var.aws_region}a"]
  public_subnets          = local.pub_subnets
  map_public_ip_on_launch = true

  enable_dns_hostnames = true
  enable_dns_support   = true
  enable_nat_gateway   = false
  single_nat_gateway   = false

  tags = local.tags
}

########################################
# AMI Amazon Linux 2023
########################################
data "aws_ami" "al2023" {
  owners      = ["amazon"]
  most_recent = true
  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

########################################
# Security Groups
########################################
resource "aws_security_group" "k8s" {
  name        = "${var.cluster_name}-k8s"
  description = "Self-Managed Kubernetes Cluster"
  vpc_id      = module.vpc.vpc_id
  tags = merge(
    local.tags,
    {
      "kubernetes" = "true"
    }
  )
}

resource "aws_vpc_security_group_ingress_rule" "intra_cluster_all" {
  security_group_id            = aws_security_group.k8s.id
  ip_protocol                  = -1
  referenced_security_group_id = aws_security_group.k8s.id
  description                  = "Allow all inter-node traffic"
}

resource "aws_vpc_security_group_egress_rule" "k8s_egress" {
  security_group_id = aws_security_group.k8s.id
  ip_protocol       = -1
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_security_group" "k6" {
  name        = "${var.cluster_name}-k6"
  description = "Client k6"
  vpc_id      = module.vpc.vpc_id
  tags        = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "nodeport_from_k6" {
  security_group_id            = aws_security_group.k8s.id
  referenced_security_group_id = aws_security_group.k6.id
  ip_protocol                  = "tcp"
  from_port                    = 30000
  to_port                      = 32000
  description                  = "NodePorts from k6"
}

resource "aws_vpc_security_group_ingress_rule" "ssh_for_k6" {
  security_group_id = aws_security_group.k6.id
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  cidr_ipv4         = "179.67.254.87/32"
}

resource "aws_vpc_security_group_egress_rule" "k6s_egress" {
  security_group_id = aws_security_group.k6.id
  ip_protocol       = -1
  cidr_ipv4         = "0.0.0.0/0"
}

############################################
# VPC Interface Endpoints SG
############################################
resource "aws_security_group" "vpce" {
  name        = "${var.cluster_name}-vpce"
  description = "Security Group for VPC Interface Endpoints"
  vpc_id      = module.vpc.vpc_id

  # Egress liberado (respostas do endpoint)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "vpce_443_from_k8s" {
  security_group_id            = aws_security_group.vpce.id
  referenced_security_group_id = aws_security_group.k8s.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  description                  = "Allow HTTPS from Kubernetes nodes"
}

resource "aws_vpc_security_group_ingress_rule" "vpce_443_from_k6" {
  security_group_id            = aws_security_group.vpce.id
  referenced_security_group_id = aws_security_group.k6.id
  ip_protocol                  = "tcp"
  from_port                    = 443
  to_port                      = 443
  description                  = "Allow HTTPS from k6 instance"
}

locals {
  vpce_subnet_ids = [module.vpc.public_subnets[0]]
}

############################################
# Interface Endpoints
############################################

# SSM
resource "aws_vpc_endpoint" "ssm" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ssm"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = local.vpce_subnet_ids
  security_group_ids  = [aws_security_group.vpce.id]
  private_dns_enabled = true
  tags                = { Name = "${var.cluster_name}-vpce-ssm" }
}
resource "aws_vpc_endpoint" "ssmmessages" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ssmmessages"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = local.vpce_subnet_ids
  security_group_ids  = [aws_security_group.vpce.id]
  private_dns_enabled = true
  tags                = { Name = "${var.cluster_name}-vpce-ssmmessages" }
}
resource "aws_vpc_endpoint" "ec2messages" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ec2messages"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = local.vpce_subnet_ids
  security_group_ids  = [aws_security_group.vpce.id]
  private_dns_enabled = true
  tags                = { Name = "${var.cluster_name}-vpce-ec2messages" }
}

# ECR
resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = local.vpce_subnet_ids
  security_group_ids  = [aws_security_group.vpce.id]
  private_dns_enabled = true
  tags                = { Name = "${var.cluster_name}-vpce-ecr-api" }
}
resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = module.vpc.vpc_id
  service_name        = "com.amazonaws.${var.aws_region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = local.vpce_subnet_ids
  security_group_ids  = [aws_security_group.vpce.id]
  private_dns_enabled = true
  tags                = { Name = "${var.cluster_name}-vpce-ecr-dkr" }
}

############################################
# Gatway Endpoint (S3)
############################################
# Use a(s) route table(s) associada(s) à sua subnet.
# Se você usa o módulo VPC, isso normalmente é module.vpc.public_route_table_ids.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc.vpc_id
  service_name      = "com.amazonaws.${var.aws_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc.public_route_table_ids

  # Política ampla (simples e funcional). Pode ser restringida depois.
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = "*",
      Action    = ["s3:GetObject", "s3:ListBucket", "s3:HeadObject", "s3:HeadBucket"],
      Resource  = ["*"]
    }]
  })

  tags = { Name = "${var.cluster_name}-vpce-s3" }
}


########################################
# IAM for SSM S3 and ECR
########################################
data "aws_iam_policy_document" "ec2_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ssm_ec2" {
  name               = "${var.cluster_name}-ssm-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ssm_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "s3" {
  role       = aws_iam_role.ssm_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "ecr_ro" {
  role       = aws_iam_role.ssm_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_instance_profile" "ssm_ec2" {
  name = "${var.cluster_name}-ssm-profile"
  role = aws_iam_role.ssm_ec2.name
}

locals {
  cp_ip = module.cp.private_ip
  worker_meta = [
    for pool, mod in module.workers : {
      ip     = mod.private_ip
      pool   = pool
      labels = local.node_pools[pool].node_labels
    }
  ]
}

resource "local_file" "inventory" {
  filename = "${path.module}/inventory.ini"
  content = templatefile("${path.module}/inventory.ini.tftpl", {
    region  = tostring(var.aws_region)
    cp_ip   = tostring(local.cp_ip)
    workers = local.worker_meta
  })
}

########################################
# ECR Private Repositories
########################################

resource "aws_ecr_repository" "znn" {
  name                 = "${var.cluster_name}/znn"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "aws_ecr_repository" "custom-self-adapter-operator" {
  name                 = "${var.cluster_name}/csa-operator"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

resource "aws_ecr_repository" "custom-self-adapter-quality" {
  name                 = "${var.cluster_name}/csa-quality-znn"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

