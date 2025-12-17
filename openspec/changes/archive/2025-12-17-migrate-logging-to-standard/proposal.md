# Change: Migrate Logging to Standard

## Why
The project currently has a mix of logging styles. To ensure consistency, type safety, and better performance, we want to enforce the use of specific Loguru patterns (f-strings and format-style) and strictly ban printf-style logging (`%s`, `%d`, etc.) as documented in `document/logging-guide.md`.

## What Changes
- Enforce f-string usage for all variable interpolation in logs.
- Enforce Loguru format-style (`{}`) as an alternative.
- Deprecate and remove all printf-style logging.
- Define explicit rules for logging usage in a new `logging` capability spec.

## Impact
- **Affected Specs**: New `logging` capability.
- **Affected Code**: potentially all python files in `core`, `services`, `infrastructure`, `interface`, `internal`, `cmd`.
