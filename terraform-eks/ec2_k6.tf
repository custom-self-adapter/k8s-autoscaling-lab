
# Selecting AMI ID
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

# SSH Key Pair
resource "tls_private_key" "k6_key" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "k6_key" {
  key_name   = "${var.cluster_name}-ssh"
  public_key = tls_private_key.k6_key.public_key_openssh
  tags       = local.tags
}

resource "local_file" "k6_pem" {
  filename        = "${path.module}/id_rsa_${var.cluster_name}"
  content         = tls_private_key.k6_key.private_key_openssh
  file_permission = "0600"
}

# Security Group
resource "aws_security_group" "k6_sg" {
  name        = "${var.cluster_name}-k6-sg"
  description = "Allows SSH inbound and all traffic outbound"
  vpc_id      = module.vpc.vpc_id
  tags        = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "k6_allow_ssh" {
  security_group_id = aws_security_group.k6_sg.id
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
  cidr_ipv4         = var.allowed_cidrs[0]
}

resource "aws_vpc_security_group_egress_rule" "k6_allow_all" {
  security_group_id = aws_security_group.k6_sg.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# EC2 Instance
module "ec2_k6" {
  source = "terraform-aws-modules/ec2-instance/aws"

  name = "${var.cluster_name}-k6"

  subnet_id                   = module.vpc.public_subnets[0]
  vpc_security_group_ids      = [aws_security_group.k6_sg.id]
  associate_public_ip_address = true

  key_name = aws_key_pair.k6_key.key_name

  instance_type = "t3a.small"

  user_data = templatefile("${path.module}/user_data_k6.sh.tftpl", {
    go_version = var.go_version
  })

  tags = local.tags
}

variable "go_version" {
  type = string
  default = "1.24.6"
}

output "k6_public_ip" {
  description = "Public IP for the K6 station intance"
  value = module.ec2_k6.public_ip
}