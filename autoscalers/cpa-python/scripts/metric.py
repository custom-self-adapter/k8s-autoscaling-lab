import os
import json
import sys
from kubernetes import client, config


def main():
    spec_raw = sys.stdin.read()
    spec = json.loads(spec_raw)
    
    containers = spec["resource"]["spec"]["template"]["spec"]["containers"]
    container_znn = [c for c in containers if c["name"] == "znn"]
    if len(container_znn) == 0:
        sys.stderr.write("Error: No container named \"znn\"")
        exit(1)
    
    sys.stdout.write("1")


if __name__ == "__main__":
    main()
