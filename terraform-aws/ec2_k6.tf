########################################
# K6 Client
########################################

module "ec2_k6" {
  source  = "terraform-aws-modules/ec2-instance/aws"
  version = "~> 6.1"

  name                        = "${var.cluster_name}-k6"
  ami                         = data.aws_ami.al2023.id
  instance_type               = "t3a.medium"
  subnet_id                   = module.vpc.public_subnets[0]
  vpc_security_group_ids      = [aws_security_group.k6.id]
  associate_public_ip_address = false
  iam_instance_profile        = aws_iam_instance_profile.ssm_ec2.name

  user_data = templatefile("${path.module}/user_data_k6.sh.tftpl", {
    go_version = var.go_version
  })

  tags = local.tags
}

variable "go_version" {
  type    = string
  default = "1.24.6"
}
