#!/usr/bin/env python3
"""Offline structural/package checks; official portable schema was separately validated."""
import json
from pathlib import Path
import re
import sys

root=Path(__file__).resolve().parents[1]
p=root/'plugins/zcode-coordinator'
portable=json.loads((p/'plugin.json').read_text())
codex=json.loads((p/'.codex-plugin/plugin.json').read_text())
market=json.loads((root/'.agents/plugins/marketplace.json').read_text())
assert portable['$schema']=='https://agent-plugins.org/schemas/1.0.0/plugin.schema.json'
assert portable['name']==codex['name']=='zcode-coordinator'
assert portable['version']==codex['version']=='0.2.0'
assert portable['license']==codex['license']=='Apache-2.0'
assert codex['skills']=='./skills/'
assert market['plugins'][0]['source']['path']=='./plugins/zcode-coordinator'
assert market['plugins'][0]['name']==portable['name']
assert (p/'LICENSE').is_file() and (p/'NOTICE').is_file()
skill=p/'skills/zcode/SKILL.md';text=skill.read_text()
assert text.startswith('---\n') and '\nname: zcode\n' in text
assert (p/'skills/zcode/scripts/zcode_job.py').is_file()
assert (p/'tests/test_jobs.py').is_file() and (p/'tests/fake_zcode.py').is_file()
for f in root.rglob('*'):
    if '.git' in f.parts or not f.is_file():continue
    assert '__pycache__' not in f.parts and f.suffix!='.pyc',f
    if f.suffix in {'.md','.json','.txt'}:
        body=f.read_text()
        assert not re.search('/'+'Users'+r'/[^/]+/',body),'personal machine path: '+str(f)
print('Portable/Codex manifests, marketplace, skill, license and clean public package: valid')
