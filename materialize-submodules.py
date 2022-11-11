#!/usr/bin/env python3
from sh import git, rm, mv
import re
import os

rm = rm.bake("-rf")
grm = git.bake("rm", "--cached")
commit = git.bake("commit", "-am")
gclone = git.bake("clone", "--recursive")
gsubtree = git.bake('subtree')
gadd = git.bake("add")
# Read the gitmodules file
submodules = {}

print("Listing submodules to materialize")
for l in git("submodule").split("\n"):
    if " " not in l:
        continue
    s = l.strip().split(" ")
    h, d = s[0], s[1]
    submodules[d] = {"path": d, "hash": h, "name": None, "url": None}

curr = None
name = None
r = re.compile(r"(submodule|path|url) [=]?[ ]?\"?([^\"]+)\"?")
for l in open(".gitmodules", "r"):
    matches = r.search(l.strip())
    if not matches:
        continue
    if matches[1] == "submodule":
        name = matches[2]
    elif matches[1] == "path":
        curr = matches[2]
        submodules[curr]["name"] = name
    elif matches[1] == "url":
        submodules[curr]["url"] = matches[2]

grm(".gitmodules")
for module in submodules.values():
    grm(module["path"])
    rm(module["path"])

    # Normalize the hashes
    module['hash'] = module['hash'].replace('-', '').replace('+', '')

commit("scripted: Remove submodules for materialization")
#mv(".gitignore", ".gitignore.bak")

for module in submodules.values():
    print(f"Cloning {module['url']} to {module['path']}")
    gsubtree(
        'add',
        f'--prefix={module["path"]}',
        module['url'],
        module['hash']
    )

# Manually add the bloody secp256k1 submodule
grm('external/libwally-core/src/secp256k1')
commit('Materializing secp256k1 submodule')
gsubtree(
    'add',
    '--prefix=external/libwally-core/src/secp256k1',
    '--squash',
    'https://github.com/ElementsProject/secp256k1-zkp.git',
    '6c0aecf72b1f4290f50302440065392715d6240a',
)

#mv(".gitignore.bak", ".gitignore")
#commit("scripted: Materialize submodules")
