---
name: java-testability-guardrails
description: Use when implementing, refactoring, testing, or reviewing Java code that changes access modifiers, exposes internal helpers, uses `@VisibleForTesting`, or adds test-only wrappers or helpers.
version: 1.0.0
---

# Java Testability Guardrails

## Overview

Choose Java access modifiers from production design and calling contracts, never from test convenience. Verify behavior through legitimate production contracts rather than exposing implementation details.

## Required Decisions

- Before widening visibility, search production call sites. If the only direct callers are tests, do not widen it.
- Keep methods used only inside their production class `private`. Do not widen `private` methods to package-private, `protected`, or `public` for direct test calls.
- Allow package-private access only when production code in the same package actually calls it, or when the target is a package-level component with an independent domain responsibility.
- Test private behavior through the public result, or through a legitimate package-level contract.
- Create expected values as fixed values or with an independent calculation. Never invoke an internal helper on the system under test to derive them.
- If the public path is excessively difficult to test, assess whether the class has too many responsibilities. Do not extract a wrapper or helper solely for tests.

## Prohibited Shortcuts

- Do not use `@VisibleForTesting` or comparable annotations to bypass access-control decisions.
- Do not add test-only production wrappers, helper methods, or components to reach internal logic.
- Do not treat a test-only caller as evidence for a production access contract.
