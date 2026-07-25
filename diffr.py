#!/usr/bin/env python3
"""diffr — CLI diff tool: compare, HTML side-by-side, patch application.

Zero dependencies. Pure Python stdlib. MIT License.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from typing import Dict, List, Optional

# ── ANSI color codes ────────────────────────────────────────────────────────

_COLORS = {
    "red": "\033[31m",
    "green": "\033[32m",
    "cyan": "\033[36m",
    "yellow": "\033[33m",
    "bold": "\033[1m",
    "reset": "\033[0m",
    "dim": "\033[2m",
}


def _color(code: str, text: str) -> str:
    return f"{_COLORS[code]}{text}{_COLORS['reset']}"


# ── HTML template for side-by-side diff ────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>diffr — {title}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace; font-size: 13px; line-height: 1.5; }}
  .header {{ background: #1a1a2e; color: #e0e0e0; padding: 12px 16px; border-bottom: 2px solid #16213e; }}
  .header h1 {{ font-size: 16px; }}
  .header span {{ color: #888; font-size: 12px; }}
  .diff-container {{ display: flex; }}
  .diff-pane {{ flex: 1; overflow-x: auto; min-width: 0; }}
  .diff-pane.left {{ border-right: 1px solid #333; }}
  .diff-pane h2 {{ background: #2a2a3e; color: #ccc; padding: 6px 12px; font-size: 12px; font-weight: normal; border-bottom: 1px solid #444; }}
  .diff-pane h2.left {{ color: #ff6b6b; }}
  .diff-pane h2.right {{ color: #51cf66; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 1px 8px; white-space: pre-wrap; word-break: break-all; }}
  td.ln {{ width: 40px; text-align: right; color: #666; user-select: none; background: #1e1e2e; border-right: 1px solid #333; }}
  tr.add {{ background: #0d3b1a; }} tr.add td.ln {{ background: #0a2e14; }}
  tr.del {{ background: #3b0d0d; }} tr.del td.ln {{ background: #2e0a0a; }}
  tr.mod {{ background: #3b3b0d; }} tr.mod td.ln {{ background: #2e2e0a; }}
  tr.same {{ background: #1a1a2e; }}
  .add-text {{ color: #51cf66; }}
  .del-text {{ color: #ff6b6b; }}
  .mod-text {{ color: #f7d44a; }}
</style>
</head>
<body>
<div class="header">
  <h1>diffr</h1>
  <span>Left: {left_label} | Right: {right_label}</span>
</div>
<div class="diff-container">
  <div class="diff-pane left">
    <h2 class="left">--- a/{left_label}</h2>
    <table>{left_table}</table>
  </div>
  <div class="diff-pane right">
    <h2 class="right">+++ b/{right_label}</h2>
    <table>{right_table}</table>
  </div>
</div>
</body>
</html>
"""


# ── CLI ────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--format", choices=["text", "json", "html"], default="text",
                        help="Output format (default: text)")

    p = argparse.ArgumentParser(
        prog="diffr",
        description="CLI diff tool: compare, HTML side-by-side, patch. Zero deps.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # compare
    cmp = sub.add_parser("compare", parents=[common],
                         help="Line-by-line diff between two files")
    cmp.add_argument("file1", help="First file to compare")
    cmp.add_argument("file2", help="Second file to compare")
    cmp.add_argument("--context", "-C", type=int, default=3,
                     help="Number of context lines (default: 3)")
    cmp.set_defaults(func=cmd_compare)

    # html
    htm = sub.add_parser("html", parents=[common],
                         help="Generate HTML side-by-side diff")
    htm.add_argument("file1", help="First file")
    htm.add_argument("file2", help="Second file")
    htm.add_argument("--output", "-o", default=None,
                     help="Output HTML file (default: stdout)")
    htm.add_argument("--context", "-C", type=int, default=3,
                     help="Number of context lines (default: 3)")
    htm.set_defaults(func=cmd_html)

    # patch
    ptc = sub.add_parser("patch", parents=[common],
                         help="Apply a unified diff patch to a file")
    ptc.add_argument("file", help="File to patch")
    ptc.add_argument("patchfile", help="Unified diff patch file to apply")
    ptc.add_argument("--dry-run", action="store_true",
                     help="Preview changes without applying")
    ptc.set_defaults(func=cmd_patch)

    return p


def _read_file(path: str) -> List[str] | None:
    """Read a file and return lines; None if file doesn't exist."""
    try:
        with open(path) as f:
            return f.readlines()
    except FileNotFoundError:
        return None


def _color_diff_line(line: str) -> str:
    """Apply ANSI color to a unified diff line."""
    if line.startswith("---") or line.startswith("+++"):
        return _color("bold", line)
    elif line.startswith("@@"):
        return _color("cyan", line)
    elif line.startswith("+"):
        return _color("green", line)
    elif line.startswith("-"):
        return _color("red", line)
    else:
        return line


def _build_html_row(cls: str, ln_left: str, text_left: str,
                    ln_right: str, text_right: str) -> tuple[str, str]:
    """Build a table row for the side-by-side HTML diff."""
    esc_left = (text_left.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;").rstrip("\n"))
    esc_right = (text_right.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace('"', "&quot;").rstrip("\n"))

    if cls == "add":
        left_row = f'<tr><td class="ln"></td><td></td></tr>'
        right_row = (f'<tr class="add"><td class="ln">{ln_right}</td>'
                     f'<td><span class="add-text">{esc_right or "&nbsp;"}</span></td></tr>')
    elif cls == "del":
        left_row = (f'<tr class="del"><td class="ln">{ln_left}</td>'
                    f'<td><span class="del-text">{esc_left or "&nbsp;"}</span></td></tr>')
        right_row = f'<tr><td class="ln"></td><td></td></tr>'
    elif cls == "mod":
        left_row = (f'<tr class="mod"><td class="ln">{ln_left}</td>'
                    f'<td><span class="mod-text">{esc_left or "&nbsp;"}</span></td></tr>')
        right_row = (f'<tr class="mod"><td class="ln">{ln_right}</td>'
                     f'<td><span class="mod-text">{esc_right or "&nbsp;"}</span></td></tr>')
    else:  # same
        left_row = (f'<tr class="same"><td class="ln">{ln_left}</td>'
                    f'<td>{esc_left or "&nbsp;"}</td></tr>')
        right_row = (f'<tr class="same"><td class="ln">{ln_right}</td>'
                     f'<td>{esc_right or "&nbsp;"}</td></tr>')

    return left_row, right_row


def _side_by_side_rows(
    a_lines: List[str], b_lines: List[str], context: int = 3
) -> tuple[List[str], List[str], List[Dict]]:
    """Produce side-by-side rows from two file contents."""
    sm = difflib.SequenceMatcher(None, a_lines, b_lines)
    left_rows = []
    right_rows = []
    changes = []

    i_a, i_b = 0, 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            # Show all or just context lines
            block = a_lines[i1:i2]
            if i1 == 0 and context is not None:
                # First block: show last `context` lines if there's more
                if len(block) > context * 2 + 1:
                    # Show first context lines, ellipsis, last context lines
                    for k in range(min(context, len(block))):
                        lr, rr = _build_html_row("same", str(i1 + k + 1), block[k],
                                                 str(j1 + k + 1), block[k])
                        left_rows.append(lr)
                        right_rows.append(rr)
                    if len(block) > context * 2:
                        gap = f'<tr class="same"><td class="ln">...</td><td>...</td></tr>'
                    left_rows.append(gap)
                    right_rows.append(gap)
                    for k in range(len(block) - context, len(block)):
                        lr, rr = _build_html_row("same", str(i1 + k + 1), block[k],
                                                 str(j1 + k + 1), block[k])
                        left_rows.append(lr)
                        right_rows.append(rr)
                else:
                    for k, line in enumerate(block):
                        lr, rr = _build_html_row("same", str(i1 + k + 1), line,
                                                 str(j1 + k + 1), line)
                        left_rows.append(lr)
                        right_rows.append(rr)
            else:
                for k, line in enumerate(block):
                    lr, rr = _build_html_row("same", str(i1 + k + 1), line,
                                             str(j1 + k + 1), line)
                    left_rows.append(lr)
                    right_rows.append(rr)

        elif tag == "replace":
            for k in range(max(i2 - i1, j2 - j1)):
                al = a_lines[i1 + k] if k < (i2 - i1) else ""
                bl = b_lines[j1 + k] if k < (j2 - j1) else ""
                aln = str(i1 + k + 1) if k < (i2 - i1) else ""
                bln = str(j1 + k + 1) if k < (j2 - j1) else ""
                lr, rr = _build_html_row("mod", aln, al, bln, bl)
                left_rows.append(lr)
                right_rows.append(rr)
            changes.append({"type": "replace", "lines_a": a_lines[i1:i2], "lines_b": b_lines[j1:j2]})

        elif tag == "delete":
            for k, line in enumerate(a_lines[i1:i2]):
                lr, rr = _build_html_row("del", str(i1 + k + 1), line, "", "")
                left_rows.append(lr)
                right_rows.append(rr)
            changes.append({"type": "delete", "lines": a_lines[i1:i2]})

        elif tag == "insert":
            for k, line in enumerate(b_lines[j1:j2]):
                lr, rr = _build_html_row("add", "", "", str(j1 + k + 1), line)
                left_rows.append(lr)
                right_rows.append(rr)
            changes.append({"type": "insert", "lines": b_lines[j1:j2]})

    return left_rows, right_rows, changes


def cmd_compare(args: argparse.Namespace) -> int:
    a_lines = _read_file(args.file1)
    b_lines = _read_file(args.file2)

    if a_lines is None:
        print(f"Error: file not found: {args.file1}", file=sys.stderr)
        return 1
    if b_lines is None:
        print(f"Error: file not found: {args.file2}", file=sys.stderr)
        return 1

    diff = list(difflib.unified_diff(
        a_lines, b_lines,
        fromfile=args.file1, tofile=args.file2,
        n=args.context,
    ))

    if args.format == "json":
        changes = []
        current = None
        for line in diff:
            if line.startswith("@@"):
                if current and current.get("lines"):
                    changes.append(current)
                current = {"hunk": line.rstrip(), "lines": []}
            elif current is not None:
                current["lines"].append(line.rstrip())
            elif line.startswith("---") or line.startswith("+++"):
                pass  # skip header for JSON
        if current and current.get("lines"):
            changes.append(current)
        print(json.dumps({
            "file1": args.file1,
            "file2": args.file2,
            "changed": len(diff) > 2,
            "changes": changes,
        }, indent=2))
    elif args.format == "html":
        left_rows, right_rows, _ = _side_by_side_rows(a_lines, b_lines, args.context)
        html = _HTML_TEMPLATE.format(
            title=f"{args.file1} vs {args.file2}",
            left_label=args.file1,
            right_label=args.file2,
            left_table="\n".join(left_rows),
            right_table="\n".join(right_rows),
        )
        print(html)
    else:
        if not diff:
            print("Files are identical.")
            return 0
        for line in diff:
            sys.stdout.write(_color_diff_line(line.rstrip()) + "\n")
    return 0


def cmd_html(args: argparse.Namespace) -> int:
    a_lines = _read_file(args.file1)
    b_lines = _read_file(args.file2)

    if a_lines is None:
        print(f"Error: file not found: {args.file1}", file=sys.stderr)
        return 1
    if b_lines is None:
        print(f"Error: file not found: {args.file2}", file=sys.stderr)
        return 1

    left_rows, right_rows, changes = _side_by_side_rows(a_lines, b_lines, args.context)

    html = _HTML_TEMPLATE.format(
        title=f"{args.file1} vs {args.file2}",
        left_label=args.file1,
        right_label=args.file2,
        left_table="\n".join(left_rows),
        right_table="\n".join(right_rows),
    )

    if args.output:
        with open(args.output, "w") as f:
            f.write(html)
        if args.format == "json":
            print(json.dumps({"output": args.output, "size": len(html),
                              "changes": len(changes)}))
        else:
            print(f"HTML diff written to: {args.output} ({len(html)} bytes, {len(changes)} changes)")
    else:
        print(html)
    return 0


def cmd_patch(args: argparse.Namespace) -> int:
    """Apply a unified diff patch to a file."""
    a_lines = _read_file(args.file)
    if a_lines is None:
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1

    patch_lines = _read_file(args.patchfile)
    if patch_lines is None:
        print(f"Error: patch file not found: {args.patchfile}", file=sys.stderr)
        return 1

    # Parse unified diff hunks and apply them
    try:
        patched = _apply_unified_diff(a_lines, patch_lines)
    except Exception as e:
        print(f"Error applying patch: {e}", file=sys.stderr)
        return 1

    if args.format == "json":
        diff_summary = list(difflib.unified_diff(a_lines, patched,
                                                 fromfile=args.file,
                                                 tofile=f"{args.file} (patched)"))
        print(json.dumps({
            "file": args.file,
            "patchfile": args.patchfile,
            "dry_run": args.dry_run,
            "applied": True if not args.dry_run else "would_apply",
            "original_lines": len(a_lines),
            "patched_lines": len(patched),
            "diff": [d.rstrip() for d in diff_summary],
        }, indent=2))
    elif args.dry_run:
        print(f"[DRY RUN] Would apply patch from '{args.patchfile}' to '{args.file}'")
        print(f"  Original: {len(a_lines)} lines")
        print(f"  Patched:  {len(patched)} lines")
        diff_lines = list(difflib.unified_diff(a_lines, patched,
                                               fromfile=args.file,
                                               tofile=f"{args.file} (patched)"))
        for line in diff_lines:
            sys.stdout.write(_color_diff_line(line.rstrip()) + "\n")
    else:
        with open(args.file, "w") as f:
            f.writelines(patched)
        print(f"Patch applied: '{args.file}' ({len(a_lines)} → {len(patched)} lines)")
    return 0


def _apply_unified_diff(original: List[str], patch: List[str]) -> List[str]:
    """Apply unified diff hunks to original content. Returns patched lines."""
    result = list(original)
    hunk_pattern = re.compile(r'^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@')
    i = 0

    # Skip header lines (---, +++)
    while i < len(patch) and (patch[i].startswith("---") or patch[i].startswith("+++")
                               or patch[i].startswith("diff ") or patch[i].startswith("index ")):
        i += 1

    offset = 0  # cumulative line offset from applied hunks
    while i < len(patch):
        line = patch[i].rstrip("\n")
        m = hunk_pattern.match(line)
        if not m:
            i += 1
            continue
        old_start = int(m.group(1)) - 1  # 0-indexed
        old_count = int(m.group(2)) if m.group(2) else 1
        new_start = int(m.group(3)) - 1
        new_count = int(m.group(4)) if m.group(4) else 1

        # Read hunk lines
        hunk_lines = []
        i += 1
        while i < len(patch):
            nxt = patch[i]
            if nxt.startswith("@@"):
                break
            if nxt.startswith("---") or nxt.startswith("+++"):
                break
            hunk_lines.append(nxt)
            i += 1

        # Apply hunk
        src_idx = old_start + offset
        new_chunk = []
        hunk_j = 0
        while hunk_j < len(hunk_lines):
            hl = hunk_lines[hunk_j]
            if hl.startswith(" "):  # context line
                new_chunk.append(hl[1:])
                hunk_j += 1
            elif hl.startswith("-"):  # remove line
                hunk_j += 1
            elif hl.startswith("+"):  # add line
                new_chunk.append(hl[1:])
                hunk_j += 1
            elif hl.startswith("\\"):  # no newline marker
                hunk_j += 1
            else:
                hunk_j += 1

        # Remove old lines and insert new
        del result[src_idx:src_idx + old_count]
        for j, nl in enumerate(new_chunk):
            result.insert(src_idx + j, nl)
        offset += len(new_chunk) - old_count

    return result


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
