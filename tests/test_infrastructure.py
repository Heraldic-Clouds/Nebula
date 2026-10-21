import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]


def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def test_inventory_preserves_complete_service_groups_and_roles(tmp_path):
    template=tmp_path/'upstream'
    template.write_text('[control]\nold\n[network]\nold\n[compute]\nold\n[monitoring]\nold\n[storage]\nold\n[deployment]\nlocalhost\n[keystone:children]\ncontrol\n[nova-compute:children]\ncompute\n')
    hosts={'controller_one':{'role':'control','address':'10.42.1.2'},'compute_one':{'role':'compute','address':'10.42.2.2'}}
    out=tmp_path/'generated'
    module('render_inventory').render(hosts,template,out,management_interface='wg0',external_interface='eth1',user='root',private_key='~/.ssh/private')
    result=(out/'multinode').read_text()
    assert '[keystone:children]\ncontrol' in result and '[nova-compute:children]\ncompute' in result
    assert 'old' not in result
    assert '10.42.2.2' in (out/'host_vars/controller_one.yml').read_text()


def test_three_controllers_require_qualified_endpoint(tmp_path):
    hosts={f'control{i}':{'role':'control','address':f'10.42.1.{i+2}'} for i in range(3)}
    hosts['compute']={'role':'compute','address':'10.42.2.2'}
    with pytest.raises(ValueError,match='qualified'):
        module('render_inventory').render(hosts,'unused',tmp_path,management_interface='wg0',external_interface='eth1',user='root',private_key='unused')


def test_preflight_fails_on_non_linux_without_fabricating_success(tmp_path,monkeypatch):
    mod=module('preflight');monkeypatch.setattr(mod.platform,'system',lambda:'Windows')
    out=tmp_path/'report.json'
    result=mod.main(['--role','compute','--management-interface','wg0','--storage-mode','verify','--output',str(out)])
    assert result==1
    report=json.loads(out.read_text())
    assert not report['passed'] and not report['nova_guest_verified']


def test_apply_and_smoke_require_explicit_approval(tmp_path):
    result=subprocess.run([sys.executable,str(ROOT/'scripts/terraform_apply.py'),str(tmp_path/'plan')],capture_output=True,text=True)
    assert result.returncode!=0 and '--approve-plan-sha256' in result.stderr
    result=subprocess.run([sys.executable,str(ROOT/'scripts/openstack_smoke.py'),'--cloud','test','--image','ubuntu','--flavor','small','--network','private','--key-name','key','--ssh-private-key','private'],capture_output=True,text=True)
    assert result.returncode!=0 and '--approve-guest-create' in result.stderr
