# CI Usage

Use Source2Launch in CI to keep generated launch material reviewable. The recommended CI output is a machine-readable promotion payload or a `launch-assets/` folder, not an automatic publish step.

## Generate Promotion JSON

```sh
source2launch promote . --platform all --json --output promotion.json
```

The JSON can be uploaded as a CI artifact and reviewed before copying content to a platform.

## Generate Launch Assets

```sh
source2launch optimize . --output launch-assets/
```

Useful review artifacts:

| File | Purpose |
| --- | --- |
| `launch-assets/INDEX.md` | reading order for reviewers |
| `launch-assets/content-review.md` | human review checklist |
| `launch-assets/campaign.json` | structured campaign plan |
| `launch-assets/platform/*.md` | platform-specific drafts |

## GitHub Actions Example

```yaml
name: source2launch

on:
  workflow_dispatch:
  pull_request:

jobs:
  launch-assets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: npm exec --package source2launch -- source2launch optimize . --output launch-assets/
        env:
          SOURCE2LAUNCH_API_KEY: ${{ secrets.SOURCE2LAUNCH_API_KEY }}
      - uses: actions/upload-artifact@v4
        with:
          name: launch-assets
          path: launch-assets/
```

## Local Check

For repositories that still want a simple local quality check, the legacy analyzer path remains available:

```sh
source2launch . --json > report.json
source2launch . --fail-under 70
```

Do not use CI to publish directly. Generate review artifacts, inspect them, then publish manually or through an official API adapter where available.
