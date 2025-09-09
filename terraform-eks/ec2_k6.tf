
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

# Security Group
resource "aws_security_group" "k6_sg" {
  name        = "${var.cluster_name}-k6-sg"
  description = "Allows all traffic outbound"
  vpc_id      = module.vpc.vpc_id
  tags        = local.tags
}

resource "aws_vpc_security_group_egress_rule" "k6_allow_all" {
  security_group_id = aws_security_group.k6_sg.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

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
  name               = "${var.cluster_name}-k6-ssm-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "ssm_managed" {
  role       = aws_iam_role.ssm_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "s3_managed" {
  role       = aws_iam_role.ssm_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_instance_profile" "ssm_ec2" {
  name = "${var.cluster_name}-k6-ssm-profile"
  role = aws_iam_role.ssm_ec2.name
}

# EC2 Instance
module "ec2_k6" {
  source = "terraform-aws-modules/ec2-instance/aws"

  name = "${var.cluster_name}-k6"

  iam_instance_profile = aws_iam_instance_profile.ssm_ec2.name

  subnet_id                   = module.vpc.public_subnets[0]
  vpc_security_group_ids      = [aws_security_group.k6_sg.id]
  associate_public_ip_address = false

  instance_type = "t3a.medium"

  user_data = templatefile("${path.module}/user_data_k6.sh.tftpl", {
    go_version = var.go_version
  })

  tags = local.tags
}

variable "go_version" {
  type    = string
  default = "1.24.6"
}
