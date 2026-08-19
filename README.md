# diffr
![CI](https://github.com/realMNohgee/Diffr/actions/workflows/ci.yml/badge.svg) ![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg) ![License](https://img.shields.io/badge/license-MIT-blue.svg)

CLI diff tool: compare, HTML side-by-side diff, and patch application.

Zero dependencies. Pure Python stdlib (difflib).

🧰 **[Tool on Hermtica Marketplace](https://hermtica.com/marketplace)**

## One Tool, Many Domains

| Domain | Use Case |
|--------|----------|
| **Developer Tools** | Quick file comparison without installing diff utilities |
| **CI/CD** | Generate HTML diff reports for PR reviews |
| **Documentation** | Side-by-side HTML diffs for changelogs and release notes |
| **Code Review** | Colored terminal diffs and patch previews |
| **Agent Workflows** | Structured diff output for AI agents to reason about changes |

## Agentic AI Framing

diffr produces machine-readable diff output in JSON and HTML formats, enabling AI agents to compare files, generate visual diff reports, and apply patches as part of automated workflows. The `--format json` output is designed for downstream consumption by other tools.

## Install

```bash
curl -O https://raw.githubusercontent.com/realMNohgee/diffr/main/diffr.py
chmod +x diffr.py
```

## Usage

```bash
# Compare two files (colored terminal output)
./diffr.py compare file1.txt file2.txt

# Compare with more context
./diffr.py compare file1.txt file2.txt --context 5

# Side-by-side HTML diff
./diffr.py html file1.py file2.py -o diff.html

# Apply a patch
./diffr.py patch file.txt changes.patch

# Dry run a patch
./diffr.py patch file.txt changes.patch --dry-run

# JSON output
./diffr.py compare file1.txt file2.txt --format json
```

## Subcommands

- `compare <file1> <file2>` — Line-by-line diff with ANSI color output
- `html <file1> <file2>` — Generate HTML side-by-side diff (dark theme)
- `patch <file> <patchfile>` — Apply a unified diff patch to a file

## License

MIT — see [LICENSE](LICENSE)
