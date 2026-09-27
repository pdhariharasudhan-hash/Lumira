---
name: Replit package installation scope
description: Package-manager installs run from the workspace root unless their target is handled separately.
---

The Replit language-package installer operates from the workspace root. Installing a frontend dependency set through it can create or rewrite root-level package manifests instead of using a nested app manifest.

**Why:** A Node dependency install created unintended root `package.json`/`package-lock.json` files and upgraded versions outside `lumira_desktop`; those artifacts had to be removed before verification.

**How to apply:** For nested applications, preserve their existing lockfile and package manifest, verify the install target, and inspect `git status` immediately after package installation.