#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dojo.settings.settings")

    if os.environ.get("DEBUG_TEST"):
        import debugpy

        debugpy.listen(("0.0.0.0", 3000))
        print("Attached!")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
