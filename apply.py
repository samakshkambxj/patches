#!/usr/bin/env python3

import sys
import subprocess
from pathlib import Path


def apply_patches(patches_root, base_repo):
    patches_root = Path(patches_root).resolve()
    base_repo = Path(base_repo).resolve()

    if not patches_root.is_dir():
        print(f"Error: patches directory not found: {patches_root}")
        sys.exit(1)

    if not base_repo.is_dir():
        print(f"Error: repo directory not found: {base_repo}")
        sys.exit(1)

    patches = sorted(patches_root.rglob("*.patch"))

    if not patches:
        print("No patches found.")
        return

    print(f"Found {len(patches)} patches\n")

    failed = []
    success = []

    for patch in patches:
        relative = patch.relative_to(patches_root)

        # __ → /
        # system__fs__fs_mgr → system/fs/fs_mgr
        # packages__apps__Settings → packages/apps/Settings
        target = relative.parent.as_posix().replace("__", "/")
        target_dir = base_repo / target

        print(f"==> {relative}")
        print(f"    Target: {target_dir}")

        if not target_dir.is_dir():
            print("    ✗ Target directory not found\n")
            failed.append(str(relative))
            continue

        result = subprocess.run(
            ["git", "am", str(patch)],
            cwd=target_dir,
            text=True,
            capture_output=True
        )

        if result.returncode == 0:
            print("    ✓ Patch Applied\n")
            success.append(str(relative))
        else:
            print("    ✗ Patch Failed")

            if result.stdout:
                print(result.stdout)

            if result.stderr:
                print(result.stderr)

            print("    Fix the conflict, then run:")
            print("      git am --continue")
            print("    or abort with:")
            print("      git am --abort\n")

            failed.append(str(relative))

    print("=" * 60)
    print(f"Applied: {len(success)}/{len(patches)}")

    if failed:
        print(f"Failed: {len(failed)}")

        for patch in failed:
            print(f"  - {patch}")

        sys.exit(1)

    print("All patches applied successfully!")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <patches_root> <android_root>")
        print(f"Example: {sys.argv[0]} ./patches ~/android")
        sys.exit(1)

    apply_patches(sys.argv[1], sys.argv[2])
