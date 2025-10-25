# tools/repo_mapper.py

**Purpose:** Key module in the repository.

**Public API:** ModuleInfo, PackageInfo, SymbolInfo, analyze, build_graph, build_hotspots, build_test_index, compute_reverse_deps, detect_language, detect_packages, discover_files, enrich_languages, evaluate_risks, extract_generic_imports, extract_python_imports, extract_python_symbols, find_tests_for, generate_json, generate_markdown, language_breakdown, main, measure_loc, mermaid_from_edges, module_name_from_path, parse_args, read_text, recommend_refactors, render_module_summary, resolve_internal_module, scan_annotations, summarize_directory_tree, write_module_summaries

**Key symbols:**
- class `SymbolInfo` (17 lines)
- class `ModuleInfo` (30 lines)
- class `PackageInfo` (13 lines)
- function `discover_files` (31 lines)
- function `detect_language` (2 lines)
- function `measure_loc` (18 lines)
- function `module_name_from_path` (11 lines)
- function `extract_python_symbols` (57 lines)
- function `extract_python_imports` (34 lines)
- function `extract_generic_imports` (46 lines)
- function `scan_annotations` (10 lines)
- function `evaluate_risks` (30 lines)
- function `read_text` (6 lines)
- function `find_tests_for` (12 lines)
- function `build_test_index` (15 lines)
- function `detect_packages` (35 lines)
- function `summarize_directory_tree` (18 lines)
- function `language_breakdown` (7 lines)
- function `build_graph` (11 lines)
- function `resolve_internal_module` (9 lines)
- function `mermaid_from_edges` (7 lines)
- function `render_module_summary` (40 lines)
- function `write_module_summaries` (6 lines)
- function `compute_reverse_deps` (7 lines)
- function `build_hotspots` (10 lines)
- function `recommend_refactors` (20 lines)
- function `generate_markdown` (50 lines)
- function `generate_json` (13 lines)
- function `enrich_languages` (8 lines)
- function `analyze` (97 lines)
- function `parse_args` (10 lines)
- function `main` (6 lines)

**Internal deps:** _None_
**External deps:** __future__, argparse, ast, collections, dataclasses, datetime, json, os, pathlib, re, sys, typing
**Used by:** _No dependents identified_

**Complexity:** 749 LOC, 29 functions, max function length 97
**Tests:** tests/test_repo_mapper.py
**Annotations:** DEPRECATED=1, FIXME=2, HACK=1, TODO=2
**Security notes:** uses eval() which can execute arbitrary code; uses exec() which can execute arbitrary code; unpickling can execute arbitrary code; yaml.load without SafeLoader can be unsafe
**Risk profile:** complexity=high, global_state=True, io_side_effects=True
