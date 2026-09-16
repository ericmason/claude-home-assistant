#!/usr/bin/env python3
"""Render a Jinja template against the live template engine.

A template that fails inside a dashboard card renders as a blank card, and a
template that fails inside an automation fails silently at runtime. Render it
here first and you see the real error with a line number.

    python3 examples/render_template.py "{{ states('sun.sun') }}"
    python3 examples/render_template.py --file my_template.j2
    python3 examples/render_template.py "{{ states.light | selectattr('state','eq','on') | list | count }}"

Endpoint: POST /api/template.
"""

import argparse
import sys
import urllib.error

from ha_ws import rest


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("template", nargs="?", help="the template text to render")
    parser.add_argument("--file", help="read the template from this file instead")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as handle:
            template = handle.read()
    elif args.template:
        template = args.template
    else:
        parser.error("pass a template as an argument or use --file")

    print(f"template: {template.strip()[:200]}")
    try:
        result = rest("/api/template", {"template": template})
    except urllib.error.HTTPError as error:
        # A bad template answers 400 with the Jinja error in the body, which is
        # the message you want. Print it rather than the status line alone.
        detail = error.read().decode(errors="replace")
        print(f"\nHTTP {error.code}: {detail}", file=sys.stderr)
        return 1

    print(f"\nrendered: {result}")
    return 0


sys.exit(main())
