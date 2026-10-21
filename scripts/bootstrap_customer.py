"""Create a real isolated Keystone customer, tenant network and scoped application credential."""
import argparse
import json
import os
from pathlib import Path
import secrets
import ipaddress
import openstack
from openstack.connection import Connection


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--admin-cloud',required=True)
    p.add_argument('--name',required=True)
    p.add_argument('--domain-id',default='default')
    p.add_argument('--external-network-id',required=True)
    p.add_argument('--ubuntu-image-id',required=True)
    p.add_argument('--flavor-id',required=True)
    p.add_argument('--tenant-cidr',default='192.168.120.0/24')
    p.add_argument('--ssh-cidr',required=True,help='Explicit trusted source CIDR for guest SSH; no public allow-all rule is added')
    p.add_argument('--output',type=Path,required=True,help='Private new directory under .runtime; never commit')
    p.add_argument('--approve-project-create',action='store_true')
    a=p.parse_args()
    if not a.approve_project_create:p.error('Explicit --approve-project-create required; no OpenStack action ran')
    ipaddress.ip_network(a.ssh_cidr)
    ipaddress.ip_network(a.tenant_cidr)
    a.output.mkdir(parents=True,exist_ok=False)
    a.output.chmod(0o700)
    admin=openstack.connect(cloud=a.admin_cloud)
    created={}
    try:
        image=admin.image.get_image(a.ubuntu_image_id)
        if image.status!='active' or image.os_distro!='ubuntu':
            p.error('Use a verified active Ubuntu image with os_distro=ubuntu')
        role=admin.identity.find_role('member',ignore_missing=False)
        project=admin.identity.create_project(name=a.name,domain_id=a.domain_id)
        created['project_id']=project.id
        password=secrets.token_urlsafe(32)
        user=admin.identity.create_user(name=a.name,domain_id=a.domain_id,password=password,default_project_id=project.id)
        created['user_id']=user.id
        admin.identity.assign_project_role_to_user(project.id,user.id,role.id)
        network=admin.network.create_network(name=a.name+'_private',project_id=project.id)
        created['network_id']=network.id
        subnet=admin.network.create_subnet(name=a.name+'_subnet',network_id=network.id,project_id=project.id,cidr=a.tenant_cidr,ip_version=4,enable_dhcp=True)
        created['subnet_id']=subnet.id
        router=admin.network.create_router(name=a.name+'_router',project_id=project.id,external_gateway_info={'network_id':a.external_network_id})
        created['router_id']=router.id
        admin.network.add_interface_to_router(router,subnet_id=subnet.id)
        auth_url=admin.config.get_auth_args()['auth_url']
        verify,cert=admin.config.get_requests_verify_args()
        if verify is False:raise RuntimeError('Do not disable OpenStack TLS verification')
        customer=Connection(auth_type='v3password',auth={'auth_url':auth_url,'user_id':user.id,'password':password,'project_id':project.id},
            region_name=admin.config.region_name,verify=verify,cert=cert,interface='internal',api_timeout=30)
        try:
            group=customer.network.find_security_group('default',ignore_missing=False)
            customer.network.create_security_group_rule(security_group_id=group.id,direction='ingress',ethertype='IPv4',
                protocol='tcp',port_range_min=22,port_range_max=22,remote_ip_prefix=a.ssh_cidr)
            cred=customer.identity.create_application_credential(user.id,name='nebula_customer',roles=[{'id':role.id}])
            secret={'project_id':project.id,'credential_id':cred.id,'credential_secret':cred.secret,'auth_url':auth_url}
            fd=os.open(a.output/'credentials.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as file:json.dump(secret,file)
        finally:customer.close()
        (a.output/'catalog.json').write_text(json.dumps({'images':[a.ubuntu_image_id],'flavors':[a.flavor_id],'networks':[network.id]},indent=2))
        print('Created customer project/network and stored scoped credentials privately. No VM or public IP was allocated.')
    finally:
        (a.output/'resources.json').write_text(json.dumps(created,indent=2))
        admin.close()


if __name__=='__main__':main()
