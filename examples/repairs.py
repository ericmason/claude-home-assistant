#!/usr/bin/env python3
"""List the open repair issues, which is where Home Assistant hides its warnings.

Repairs are the notices you see under Settings, and they are the fastest read
on whether something broke recently: a deprecated YAML key, an integration that
lost its credentials, a device that vanished.

    python3 examples/repairs.py
    python3 examples/repairs.py --all

Message types: repairs/list_issues.
"""

import argparse
import asyncio

from ha_ws import call, connect


async def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--all",
        action="store_true",
        help="include issues you already dismissed",
    )
    args = parser.parse_args()

    async with connect() as ws:
        result = await call(ws, {"type": "repairs/list_issues"})

    issues = result.get("issues", []) if isinstance(result, dict) else result
    if not args.all:
        issues = [issue for issue in issues if not issue.get("dismissed_version")]

    print(f"{len(issues)} repair issue(s)")
    for issue in sorted(issues, key=lambda item: item.get("domain", "")):
        severity = issue.get("severity", "")
        fixable = "fixable" if issue.get("is_fixable") else "not fixable"
        print(f"\n  {issue.get('domain')}: {issue.get('issue_id')}")
        print(f"    severity {severity}, {fixable}")
        if issue.get("translation_placeholders"):
            print(f"    details  {issue['translation_placeholders']}")
        if issue.get("learn_more_url"):
            print(f"    more     {issue['learn_more_url']}")


asyncio.run(main())
