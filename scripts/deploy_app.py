"""Run from the checkout on an approved ThreeFold application host (pilot: controller)."""
import argparse
from pathlib import Path
import subprocess
from nebula.config import settings


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--production',action='store_true')
    a=p.parse_args()
    cfg=settings()
    if not Path('.env').exists() or not cfg.credential_key:
        p.error('Run nebula init-env and configure .env privately first')
    command=['docker','compose','-f','compose.yml']
    if a.production:
        if not cfg.cookie_secure or not cfg.public_url.startswith('https://'):
            p.error('Public deployment requires HTTPS NEBULA_PUBLIC_URL and NEBULA_COOKIE_SECURE=true')
        command+=['-f','compose.production.yml']
    subprocess.run(command+['up','--build','-d'],check=True)
    subprocess.run(command+['ps'],check=True)
    print('Containers started. Verify /api/v1/health/ready and the customer/VM/payment acceptance flow before enabling provisioning.')


if __name__=='__main__':main()
