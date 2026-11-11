# Governance — single-maintainer residual risk

Status: **accepted residual risk**.

`main` branch protection is configured with:

- Require a pull request before merging: **yes**
- Required approving reviews: **0**
- Required status checks: **`cbp-gate`** (strict / up to date)
- Include administrators: **yes**
- Allow force pushes: **no**
- Allow deletions: **no**
- Tag ruleset `protect-release-tags`: `refs/tags/v*`, update/delete blocked,
  no bypass actors.

## Why reviews = 0

The project currently has one human maintainer (`JunxiangPan`). GitHub does not
allow the author to approve their own pull request, so requiring one approval
would make every PR permanently unmergeable.

## Residual risk

There is **no second-person review** during the single-maintainer period.
Compensating controls are the required `cbp-gate`, strict branch-up-to-date
checks, administrator enforcement, immutable release tags, and the opt-in
`--profile strict` evidence gate. These do not replace independent human
review.

## Revisit trigger

When a second human maintainer is added, restore
`required_approving_review_count` to **1**. Do not remove `cbp-gate` or the tag
ruleset to compensate.
