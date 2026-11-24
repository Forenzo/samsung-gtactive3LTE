#!/usr/bin/env python3
"""Audit every current remote branch without printing endpoint strings.

Read-only. Finds filenames with IPv4 literals or IPv6 link-local prefixes.
Excludes bundled upstream U-Boot from the detailed first-party listing.
Does not inspect historical commits not at branch heads.
"""
import subprocess

def output(*cmd):
    return subprocess.check_output(cmd, text=True)

refs=output("git","for-each-ref","--format=%(refname)","refs/remotes/origin").splitlines()
refs=[r for r in refs if r!="refs/remotes/origin/HEAD"]
print("Current remote branches scanned:", len(refs))
for ref in refs:
    p=subprocess.run([
        "git","grep","-I","-l","-E",
        "-e",r"([0-9]{1,3}\.){3}[0-9]{1,3}",
        "-e",r"fe[89aAbB][0-9a-fA-F]*:",
        ref,"--",":(exclude)bootchain/u-boot",":(exclude)bootchain/uniLoader",
    ],capture_output=True,text=True)
    if p.returncode not in (0,1):
        raise RuntimeError(f"git grep failed for {ref}: {p.stderr[:200]}")
    lines=p.stdout.splitlines()
    paths=[line[len(ref)+1:] for line in lines if line.startswith(ref+":")]
    public=ref.removeprefix("refs/remotes/origin/")
    print(f"BRANCH {public}: {len(paths)} first-party/nonvendored files with candidates")
    for path in paths[:75]:
        print(f"  {path}")
    if len(paths)>75:
        print(f"  ... {len(paths)-75} additional paths (not printed)")
print("No literal IP addresses or login names printed.")
