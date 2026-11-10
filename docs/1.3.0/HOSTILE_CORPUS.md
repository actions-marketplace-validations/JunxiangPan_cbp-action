# CBP 1.3.0 — hostile input corpus

`tests/hostile/corpus.json` contains **50** entries. Every entry has
`"expect": "FAIL"`; `tests/test_hostile_corpus.py` runs all of them.

| Category | Cases | What is rejected |
|---|---:|---|
| composite_action | 5 | expression injection, shell metacharacters, backticks, newlines |
| checkout_ref | 5 | `../`, command substitution, leading `-`, newlines |
| permissions | 5 | `write-all`, write contents/actions, read id-token, unknown keys |
| artifact_name | 6 | shell metacharacters, traversal, slash/backslash, reserved names, spaces |
| tar_slip | 6 | absolute paths, drive letters, UNC, `..` traversal |
| crlf_unicode | 8 | CRLF/CR, NUL/control, NFD, bidi and zero-width characters |
| case_backslash | 6 | Windows reserved names, backslash traversal, duplicate separators |
| invalid_json | 6 | duplicate keys, truncated JSON, trailing garbage, NaN, NUL in strings |
| misc | 3 | bidi, backslash path, overlong artifact name |

Result: **50/50 rejected**, 0 accepted. This is a parser/validator corpus, not a
claim that CBP stops a malicious runner or a compromised maintainer.
