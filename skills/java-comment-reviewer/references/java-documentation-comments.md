# Java Documentation Comments

When creating new Java code or making meaningful changes to existing Java code, review documentation comments before considering the implementation complete.

## Comment Language

- All Javadoc and inline comments in Java code must be written in Korean.
- Do not write Java comments in English unless the text is a fixed external identifier, protocol term, API field name, or quoted specification text that should not be translated.

## When To Write Javadoc

- Add Javadoc to every new public class, interface, and enum to describe its role and responsibility.
- Add Javadoc to every new public or protected method to describe its purpose, key parameters, return value, and exceptional conditions.
- For external API integrations, configuration binding, DTOs, events, schedulers, and other contract-oriented types, document field meanings when other developers need that contract to be explicit.
- For tests, add a class-level or key assertion comment when `DisplayName` alone is not enough to explain what is being verified.

## When To Write Inline Comments

- Review inline comments regardless of access modifier. The deciding factor is whether a reader can understand the domain policy, exceptional fallback, or external contract from the code alone.
- Add short inline comments for transformations, fallbacks, security reasoning, and external specification compliance points when the intent is not obvious from code alone.
- Explain why logic handles API keys, tokens, personal data, file Data URLs, trace/session data, or other sensitive data in a particular way.
- Do not add comments for simple assignments, getter calls, or builder field lists where the code already explains itself.

## Before Completion

- When adding a new file, review the entire file for missing Javadoc.
- When modifying an existing file, review the changed public surface and complex private helpers for necessary comments.
- Comments must match the current behavior. Update related Javadoc and inline comments whenever implementation behavior changes.
