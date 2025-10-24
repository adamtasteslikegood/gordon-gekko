#!/usr/bin/env python3
"""Repository mapping tool.

This module walks a repository tree, computes lightweight static analysis
metrics, and emits documentation/JSON artifacts describing the codebase.
It is intentionally stdlib-only so it can run in restricted environments.
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "out",
    ".next",
    ".turbo",
    "coverage",
    ".cache",
    ".venv",
    "venv",
    "env",
    "target",
    "bin",
    "obj",
    "vendor",
    ".terraform",
    ".gradle",
    "Pods",
}

LANG_EXTENSIONS = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".c": "C",
    ".h": "C",
    ".hpp": "C++",
    ".cpp": "C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".tf": "Terraform",
    ".sh": "Shell",
    ".sql": "SQL",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".json": "JSON",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "INI",
    ".md": "Markdown",
}

TEXT_EXTENSIONS = {"Markdown", "YAML", "JSON", "TOML", "INI"}

TEST_FILE_PATTERNS = (
    re.compile(r"(^|/)test_[^/]+\.[a-z0-9]+$"),
    re.compile(r"(^|/)[^/]+(_test|_spec)\.[a-z0-9]+$"),
)

ANNOTATION_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|DEPRECATED)\b")
COMPLEXITY_TOKENS = re.compile(r"\b(if|for|while|case|switch|catch|elif|try|except|and|or|&&|\|\|)\b")
GLOBAL_STATE_TOKENS = re.compile(r"\b(global|nonlocal|static)\b")
IO_SIDE_EFFECT_TOKENS = re.compile(r"\b(open|requests\.|httpx\.|subprocess|socket|os\.system)\b")
SECURITY_TOKENS = {
    "eval": "uses eval() which can execute arbitrary code",
    "exec": "uses exec() which can execute arbitrary code",
    "pickle.loads": "unpickling can execute arbitrary code",
    "yaml.load": "yaml.load without SafeLoader can be unsafe",
}


@dataclass
class SymbolInfo:
    name: str
    kind: str
    lines: int
    doc: Optional[str]

    def to_dict(self) -> Dict[str, object]:
        data = {
            "name": self.name,
            "kind": self.kind,
            "lines": self.lines,
        }
        if self.doc:
            data["doc"] = self.doc.strip().splitlines()[0][:200]
        else:
            data["doc"] = ""
        return data


@dataclass
class ModuleInfo:
    path: str
    language: str
    loc: int
    exports: List[str]
    public_api: List[str]
    imports_internal: List[str]
    imports_external: List[str]
    defined_symbols: List[SymbolInfo]
    tests: Dict[str, object]
    annotations: Dict[str, int]
    risks: Dict[str, object]
    module_name: str
    functions: int
    max_function_length: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "language": self.language,
            "loc": self.loc,
            "exports": self.exports,
            "public_api": self.public_api,
            "imports_internal": self.imports_internal,
            "imports_external": self.imports_external,
            "defined_symbols": [s.to_dict() for s in self.defined_symbols],
            "tests": self.tests,
            "annotations": self.annotations,
            "risks": self.risks,
        }


@dataclass
class PackageInfo:
    name: str
    path: str
    type: str
    deps: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "path": self.path,
            "type": self.type,
            "deps": sorted(set(self.deps)),
        }


def discover_files(root: Path, extra_ignored: Optional[Sequence[Path]] = None) -> Iterator[Path]:
    root = root.resolve()
    skip_paths = [p.resolve() for p in extra_ignored or []]

    def is_skipped(path: Path) -> bool:
        for skip in skip_paths:
            try:
                path.resolve().relative_to(skip)
                return True
            except ValueError:
                continue
        return False

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath).resolve()
        dirnames[:] = [
            d
            for d in dirnames
            if d not in IGNORED_DIRS
            and not d.startswith(".")
            and not is_skipped(current / d)
        ]
        for filename in filenames:
            path = Path(dirpath, filename)
            if path.is_symlink():
                continue
            if path.stat().st_size > 1_000_000:
                continue
            if is_skipped(path):
                continue
            yield path


def detect_language(path: Path) -> str:
    return LANG_EXTENSIONS.get(path.suffix.lower(), "Unknown")


def measure_loc(path: Path, language: str) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            lines = 0
            for raw in handle:
                stripped = raw.strip()
                if not stripped:
                    continue
                if language == "Python" and stripped.startswith("#"):
                    continue
                if language in {"JavaScript", "TypeScript", "Java", "Go", "C", "C++", "C#"} and stripped.startswith("//"):
                    continue
                if language in TEXT_EXTENSIONS and stripped.startswith("#"):
                    continue
                lines += 1
            return lines
    except (OSError, UnicodeDecodeError):
        return 0


def module_name_from_path(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    parts = list(rel.parts)
    if parts and parts[0] in {"src", "lib"}:
        parts = parts[1:]
    if parts:
        parts[-1] = parts[-1].rsplit(".", 1)[0]
    name = ".".join(p for p in parts if p)
    if name.endswith(".__init__"):
        name = name[: -len(".__init__")]
    return name


def extract_python_symbols(path: Path) -> Tuple[List[str], List[SymbolInfo], int, int]:
    exports: List[str] = []
    symbols: List[SymbolInfo] = []
    functions = 0
    max_len = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            source = handle.read()
    except (OSError, UnicodeDecodeError):
        return exports, symbols, functions, max_len

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return exports, symbols, functions, max_len

    public = []
    explicit_all: Optional[List[str]] = None

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    explicit_all = []
                    if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                explicit_all.append(elt.value)
                    break

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # type: ignore[override]
            nonlocal functions, max_len
            functions += 1
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            max_len = max(max_len, length)
            doc = ast.get_docstring(node)
            symbols.append(SymbolInfo(name=node.name, kind="function", lines=length, doc=doc))
            if not node.name.startswith("_"):
                public.append(node.name)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node: ast.ClassDef) -> None:  # type: ignore[override]
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            doc = ast.get_docstring(node)
            symbols.append(SymbolInfo(name=node.name, kind="class", lines=length, doc=doc))
            if not node.name.startswith("_"):
                public.append(node.name)

    Visitor().visit(tree)

    if explicit_all is not None:
        exports = explicit_all
    else:
        exports = sorted(public)
    return exports, symbols, functions, max_len


def extract_python_imports(path: Path, internal_roots: Sequence[str]) -> Tuple[List[str], List[str]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            source = handle.read()
    except (OSError, UnicodeDecodeError):
        return [], []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], []

    internal: List[str] = []
    external: List[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[0]
                if name in internal_roots:
                    internal.append(alias.name)
                else:
                    external.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                continue
            name = module.split(".")[0] if module else ""
            full = module if module else ""
            if name and name in internal_roots:
                internal.append(full)
            elif module:
                external.append(module)
    return sorted(set(internal)), sorted(set(external))


def extract_generic_imports(path: Path, language: str, internal_roots: Sequence[str]) -> Tuple[List[str], List[str]]:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            content = handle.read()
    except OSError:
        return [], []

    internal: List[str] = []
    external: List[str] = []

    if language in {"JavaScript", "TypeScript"}:
        pattern = re.compile(r"import\s+(?:.+?\s+from\s+)?['\"]([^'\"]+)['\"]")
        for match in pattern.finditer(content):
            target = match.group(1)
            first = target.split("/")[0].split(".")[0]
            if first in internal_roots:
                internal.append(target)
            else:
                external.append(target)
    elif language == "Go":
        single_pattern = re.compile(r"import\s+\"([^\"]+)\"")
        for match in single_pattern.finditer(content):
            target = match.group(1)
            first = target.split("/")[0]
            if first in internal_roots:
                internal.append(target)
            else:
                external.append(target)
        block_pattern = re.compile(r"import\s*\((.*?)\)", re.DOTALL)
        for block in block_pattern.finditer(content):
            for target in re.findall(r"\"([^\"]+)\"", block.group(1)):
                first = target.split("/")[0]
                if first in internal_roots:
                    internal.append(target)
                else:
                    external.append(target)
    else:
        pattern = re.compile(r"^\s*#include\s+[<\"]([^>\"]+)[>\"]", re.MULTILINE)
        for match in pattern.finditer(content):
            target = match.group(1)
            first = target.split("/")[0]
            if first in internal_roots:
                internal.append(target)
            else:
                external.append(target)
    return sorted(set(internal)), sorted(set(external))


def scan_annotations(path: Path) -> Dict[str, int]:
    counts = Counter()
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                for match in ANNOTATION_PATTERN.finditer(line):
                    counts[match.group(1).lower()] += 1
    except OSError:
        pass
    return dict(counts)


def evaluate_risks(content: str, loc: int, language: str) -> Dict[str, object]:
    if language in TEXT_EXTENSIONS:
        return {
            "complexity": "low",
            "global_state": False,
            "io_side_effects": False,
            "security_notes": [],
        }
    complexity_hits = len(COMPLEXITY_TOKENS.findall(content))
    complexity_level = "low"
    if loc > 400 or complexity_hits > 150:
        complexity_level = "high"
    elif loc > 120 or complexity_hits > 40:
        complexity_level = "medium"
    elif loc > 60 or complexity_hits > 20:
        complexity_level = "elevated"

    global_state = bool(GLOBAL_STATE_TOKENS.search(content))
    io_side_effects = bool(IO_SIDE_EFFECT_TOKENS.search(content))
    security_notes: List[str] = []
    for token, message in SECURITY_TOKENS.items():
        if token in content:
            security_notes.append(message)

    return {
        "complexity": complexity_level,
        "global_state": global_state,
        "io_side_effects": io_side_effects,
        "security_notes": security_notes,
    }


def read_text(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return handle.read()
    except OSError:
        return ""


def find_tests_for(module_path: Path, root: Path, test_index: Dict[str, List[str]]) -> Dict[str, object]:
    rel = module_path.relative_to(root)
    stem = module_path.stem
    matches = []
    for key, paths in test_index.items():
        if stem in key:
            matches.extend(paths)
    rel_str = str(rel)
    if rel_str in test_index:
        matches.extend(test_index[rel_str])
    matches = sorted(set(matches))
    return {"present": bool(matches), "paths": matches}


def build_test_index(root: Path) -> Dict[str, List[str]]:
    index: Dict[str, List[str]] = defaultdict(list)
    for path in discover_files(root):
        rel = path.relative_to(root)
        rel_str = str(rel)
        if not any(pattern.search(rel_str) for pattern in TEST_FILE_PATTERNS):
            continue
        key = rel_str.replace(os.sep, "/")
        index[key].append(key)
        stem = path.stem
        index[stem].append(key)
        parent = "/".join(rel.parts[:-1])
        if parent:
            index[parent].append(key)
    return index


def detect_packages(root: Path) -> Dict[str, PackageInfo]:
    packages: Dict[str, PackageInfo] = {}
    for path in root.rglob("__init__.py"):
        try:
            pkg_path = path.parent.relative_to(root)
        except ValueError:
            continue
        parts = list(pkg_path.parts)
        base_prefix = []
        if parts and parts[0] == "src":
            base_prefix = ["src"]
            parts = parts[1:]
        if not parts:
            continue
        root_name = parts[0]
        if base_prefix:
            rel_path = Path(*base_prefix, root_name)
        else:
            rel_path = Path(root_name)
        packages.setdefault(
            root_name,
            PackageInfo(
                name=root_name,
                path=str(rel_path),
                type="lib",
                deps=[],
            ),
        )
    main_entry = root / "main.py"
    if main_entry.exists():
        packages.setdefault(
            "main",
            PackageInfo(name="main", path="main.py", type="app", deps=[]),
        )
    return packages


def summarize_directory_tree(root: Path, modules: Sequence[ModuleInfo], max_depth: int = 3) -> str:
    tree_counts: Dict[Tuple[str, ...], Dict[str, int]] = defaultdict(lambda: {"files": 0, "loc": 0})
    for module in modules:
        rel = Path(module.path)
        parts = rel.parts
        for depth in range(1, min(len(parts), max_depth) + 1):
            key = tuple(parts[:depth])
            tree_counts[key]["files"] += 1
            tree_counts[key]["loc"] += module.loc

    lines: List[str] = []
    sorted_keys = sorted(tree_counts.keys())
    for key in sorted_keys:
        indent = "  " * (len(key) - 1)
        name = key[-1]
        data = tree_counts[key]
        lines.append(f"{indent}- {'/'.join(key)} (files: {data['files']}, loc: {data['loc']})")
    return "\n".join(lines)


def language_breakdown(modules: Sequence[ModuleInfo]) -> Tuple[Dict[str, int], Dict[str, int]]:
    loc_counter: Counter[str] = Counter()
    file_counter: Counter[str] = Counter()
    for module in modules:
        loc_counter[module.language] += module.loc
        file_counter[module.language] += 1
    return dict(loc_counter), dict(file_counter)


def build_graph(modules: Sequence[ModuleInfo], module_map: Dict[str, ModuleInfo]) -> Dict[str, object]:
    nodes = []
    edges = []
    for module in modules:
        nodes.append({"id": module.path, "label": module.module_name or module.path, "type": "module"})
    for module in modules:
        for target in module.imports_internal:
            resolved = resolve_internal_module(target, module_map)
            if resolved:
                edges.append({"from": module.path, "to": resolved.path, "type": "import"})
    return {"nodes": nodes, "edges": edges}


def resolve_internal_module(target: str, module_map: Dict[str, ModuleInfo]) -> Optional[ModuleInfo]:
    if target in module_map:
        return module_map[target]
    if target + ".__init__" in module_map:
        return module_map[target + ".__init__"]
    for name, module in module_map.items():
        if name.startswith(target + "."):
            return module
    return None


def mermaid_from_edges(edges: Sequence[Dict[str, str]], limit: int = 100) -> str:
    lines = ["flowchart LR"]
    for edge in edges[:limit]:
        lines.append(f"    \"{edge['from']}\" --> \"{edge['to']}\"")
    if len(edges) > limit:
        lines.append(f"    %% {len(edges) - limit} edges omitted for brevity")
    return "\n".join(lines)


def render_module_summary(module: ModuleInfo, reverse_deps: Dict[str, List[str]]) -> str:
    lines = [f"# {module.path}", ""]
    purpose = "Key module in the repository." if module.exports else "Utility or configuration module."
    lines.append(f"**Purpose:** {purpose}")
    lines.append("")
    if module.public_api:
        lines.append("**Public API:** " + ", ".join(module.public_api))
    else:
        lines.append("**Public API:** _None declared_")
    lines.append("")
    if module.defined_symbols:
        lines.append("**Key symbols:**")
        for symbol in module.defined_symbols:
            doc = symbol.doc.strip().splitlines()[0] if symbol.doc else ""
            doc_fragment = f" — {doc}" if doc else ""
            lines.append(f"- {symbol.kind} `{symbol.name}` ({symbol.lines} lines){doc_fragment}")
    else:
        lines.append("**Key symbols:** _No structured symbols parsed_")
    lines.append("")
    lines.append("**Internal deps:** " + (", ".join(module.imports_internal) if module.imports_internal else "_None_"))
    lines.append("**External deps:** " + (", ".join(module.imports_external) if module.imports_external else "_None_"))
    rev = reverse_deps.get(module.path, [])
    lines.append("**Used by:** " + (", ".join(rev) if rev else "_No dependents identified_"))
    lines.append("")
    lines.append(f"**Complexity:** {module.loc} LOC, {module.functions} functions, max function length {module.max_function_length}")
    test_paths = module.tests.get("paths", [])
    lines.append("**Tests:** " + (", ".join(test_paths) if test_paths else "_No tests located_"))
    if module.annotations:
        annot = ", ".join(f"{k.upper()}={v}" for k, v in sorted(module.annotations.items()))
    else:
        annot = "None"
    lines.append(f"**Annotations:** {annot}")
    if module.risks.get("security_notes"):
        notes = "; ".join(module.risks["security_notes"])
    else:
        notes = "None"
    lines.append(f"**Security notes:** {notes}")
    lines.append(f"**Risk profile:** complexity={module.risks.get('complexity')}, global_state={module.risks.get('global_state')}, io_side_effects={module.risks.get('io_side_effects')}")
    lines.append("")
    return "\n".join(lines)


def write_module_summaries(modules: Sequence[ModuleInfo], output_dir: Path, reverse_deps: Dict[str, List[str]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for module in modules:
        safe_name = module.path.replace(os.sep, "__").replace("/", "__")
        path = output_dir / f"{safe_name}.md"
        path.write_text(render_module_summary(module, reverse_deps), encoding="utf-8")


def compute_reverse_deps(edges: Sequence[Dict[str, str]]) -> Dict[str, List[str]]:
    reverse: Dict[str, List[str]] = defaultdict(list)
    for edge in edges:
        reverse[edge["to"]].append(edge["from"])
    for key in reverse:
        reverse[key] = sorted(set(reverse[key]))
    return reverse


def build_hotspots(modules: Sequence[ModuleInfo], reverse: Dict[str, List[str]]) -> List[str]:
    sorted_by_loc = sorted(modules, key=lambda m: m.loc, reverse=True)[:5]
    sorted_by_fanin = sorted(modules, key=lambda m: len(reverse.get(m.path, [])), reverse=True)[:5]
    missing_tests = [m for m in modules if not m.tests.get("present")] [:5]

    lines = ["### Hotspots", ""]
    lines.append("- Largest modules: " + ", ".join(f"{m.path} ({m.loc} LOC)" for m in sorted_by_loc))
    lines.append("- Most dependents: " + ", ".join(f"{m.path} ({len(reverse.get(m.path, []))})" for m in sorted_by_fanin))
    lines.append("- Modules without tests: " + ", ".join(m.path for m in missing_tests) if missing_tests else "- All modules have associated tests")
    return lines


def recommend_refactors(modules: Sequence[ModuleInfo], reverse: Dict[str, List[str]]) -> List[str]:
    recs: List[str] = []
    heavy = [m for m in modules if m.loc > 200]
    if heavy:
        recs.append("Break down the largest modules (" + ", ".join(m.path for m in heavy[:3]) + ") into smaller units.")
    high_complex = [m for m in modules if m.risks.get("complexity") in {"high", "elevated"}]
    if high_complex:
        recs.append("Review complex modules for maintainability: " + ", ".join(m.path for m in high_complex[:3]))
    untested = [m for m in modules if not m.tests.get("present")]
    if untested:
        recs.append("Add tests for modules without coverage, starting with " + ", ".join(m.path for m in untested[:3]))
    io_modules = [m for m in modules if m.risks.get("io_side_effects")]
    if io_modules:
        recs.append("Ensure IO-heavy modules have error handling and timeouts: " + ", ".join(m.path for m in io_modules[:3]))
    annotations = [m for m in modules if m.annotations]
    if annotations:
        recs.append("Resolve outstanding annotations (TODO/FIXME) in " + ", ".join(m.path for m in annotations[:3]))
    if not recs:
        recs.append("Codebase is in good shape; focus on incremental improvements.")
    return recs


def generate_markdown(
    root: Path,
    modules: Sequence[ModuleInfo],
    packages: Sequence[PackageInfo],
    graph: Dict[str, object],
    breakdown_loc: Dict[str, int],
    breakdown_files: Dict[str, int],
) -> str:
    total_loc = sum(m.loc for m in modules)
    total_files = len(modules)
    tree = summarize_directory_tree(root, modules)
    generated_ts = _dt.datetime.now(_dt.timezone.utc).isoformat()
    lines = ["# Repository Map", ""]
    lines.append(f"Generated: {generated_ts}")
    lines.append("")
    lines.append("## Overview")
    lines.append(f"- Total modules: {total_files}")
    lines.append(f"- Total LOC (approx): {total_loc}")
    lines.append("")
    lines.append("## Directory Tree (depth ≤ 3)")
    lines.append("```")
    lines.append(tree)
    lines.append("```")
    lines.append("")
    lines.append("## Language Breakdown")
    lines.append("| Language | LOC | Files |")
    lines.append("| --- | ---: | ---: |")
    for language in sorted(breakdown_loc.keys()):
        loc = breakdown_loc[language]
        files = breakdown_files.get(language, 0)
        percent_loc = (loc / total_loc * 100) if total_loc else 0
        percent_files = (files / total_files * 100) if total_files else 0
        lines.append(f"| {language} | {loc} ({percent_loc:.1f}%) | {files} ({percent_files:.1f}%) |")
    lines.append("")
    lines.append("## Packages")
    for pkg in packages:
        lines.append(f"- **{pkg.name}** ({pkg.type}) — path: `{pkg.path}`, deps: {', '.join(pkg.deps) if pkg.deps else 'none'}")
    lines.append("")
    lines.append("## Dependency Graph (top edges)")
    lines.append("```mermaid")
    lines.append(mermaid_from_edges(graph["edges"]))
    lines.append("```")
    lines.append("")
    reverse = compute_reverse_deps(graph["edges"])
    lines.extend(build_hotspots(modules, reverse))
    lines.append("")
    lines.append("## Key Insights & Recommended Refactors")
    for insight in recommend_refactors(modules, reverse):
        lines.append(f"- {insight}")
    return "\n".join(lines)


def generate_json(
    modules: Sequence[ModuleInfo],
    packages: Sequence[PackageInfo],
    graph: Dict[str, object],
) -> Dict[str, object]:
    generated_ts = _dt.datetime.now(_dt.timezone.utc).isoformat()
    return {
        "generated_at": generated_ts,
        "languages": {},
        "packages": [pkg.to_dict() for pkg in packages],
        "modules": [module.to_dict() for module in modules],
        "graph": graph,
    }


def enrich_languages(json_payload: Dict[str, object], breakdown_loc: Dict[str, int], breakdown_files: Dict[str, int]) -> None:
    languages = {}
    for language, loc in breakdown_loc.items():
        languages[language] = {
            "loc": loc,
            "files": breakdown_files.get(language, 0),
        }
    json_payload["languages"] = languages


def analyze(root: Path, output_dir: Path) -> Dict[str, object]:
    root = root.resolve()
    output_dir = output_dir.resolve()
    skip_dirs: List[Path] = []
    if output_dir.is_relative_to(root):
        skip_dirs.append(output_dir)
    files = list(discover_files(root, skip_dirs))
    packages_map = detect_packages(root)
    internal_roots = sorted(packages_map.keys())
    test_index = build_test_index(root)

    modules: List[ModuleInfo] = []
    module_map: Dict[str, ModuleInfo] = {}

    for path in files:
        if path.is_dir():
            continue
        language = detect_language(path)
        if language == "Unknown":
            continue
        loc = measure_loc(path, language)
        content = read_text(path)
        annotations = scan_annotations(path)
        risks = evaluate_risks(content, loc, language)
        module_name = module_name_from_path(path, root)
        exports: List[str] = []
        symbols: List[SymbolInfo] = []
        functions = 0
        max_function_length = 0
        if language == "Python":
            exports, symbols, functions, max_function_length = extract_python_symbols(path)
            imports_internal, imports_external = extract_python_imports(path, internal_roots)
        else:
            imports_internal, imports_external = extract_generic_imports(path, language, internal_roots)
        tests = find_tests_for(path, root, test_index)
        module = ModuleInfo(
            path=str(path.relative_to(root)),
            language=language,
            loc=loc,
            exports=exports,
            public_api=exports,
            imports_internal=imports_internal,
            imports_external=imports_external,
            defined_symbols=symbols,
            tests=tests,
            annotations=annotations,
            risks=risks,
            module_name=module_name,
            functions=functions,
            max_function_length=max_function_length,
        )
        modules.append(module)
        if module_name:
            module_map[module_name] = module

    graph = build_graph(modules, module_map)
    reverse = compute_reverse_deps(graph["edges"])

    # Update package dependencies
    for module in modules:
        origin_package = module.module_name.split(".")[0] if module.module_name else None
        for target in module.imports_internal:
            resolved = resolve_internal_module(target, module_map)
            if not resolved:
                continue
            target_package = resolved.module_name.split(".")[0] if resolved.module_name else None
            if origin_package and target_package and origin_package != target_package:
                packages_map.setdefault(origin_package, PackageInfo(origin_package, origin_package, "lib", []))
                packages_map.setdefault(target_package, PackageInfo(target_package, target_package, "lib", []))
                packages_map[origin_package].deps.append(target_package)

    packages = sorted(packages_map.values(), key=lambda p: p.name)

    breakdown_loc, breakdown_files = language_breakdown(modules)

    output_dir.mkdir(parents=True, exist_ok=True)
    docs_json = generate_json(modules, packages, graph)
    enrich_languages(docs_json, breakdown_loc, breakdown_files)
    (output_dir / "repo-map.json").write_text(json.dumps(docs_json, indent=2), encoding="utf-8")
    (output_dir / "repo-map.md").write_text(
        generate_markdown(root, modules, packages, graph, breakdown_loc, breakdown_files),
        encoding="utf-8",
    )
    (output_dir / "dependency-graph.mmd").write_text(
        mermaid_from_edges(graph["edges"]),
        encoding="utf-8",
    )
    summaries_dir = output_dir / "module-summaries"
    write_module_summaries(modules, summaries_dir, reverse)

    return {
        "modules": modules,
        "packages": packages,
        "graph": graph,
        "breakdown_loc": breakdown_loc,
        "breakdown_files": breakdown_files,
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate repository maps")
    parser.add_argument("--root", type=str, default=".", help="Repository root path")
    parser.add_argument(
        "--output",
        type=str,
        default="docs",
        help="Output directory for generated artifacts",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    root = Path(args.root)
    output_dir = Path(args.output)
    analyze(root, output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
