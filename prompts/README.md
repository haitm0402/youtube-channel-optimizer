# Structured prompt assets

UTF-8 Markdown templates loaded by `core.prompts.PromptLoader`. Render `${name}`
variables with `PromptRenderer`; use `$$` for a literal dollar. JSON braces and
future title slots such as `{artist}` do not require escaping. Inserted input is
not recursively rendered. Missing files, invalid UTF-8, syntax, or variables raise
`PromptError`. New prompts can be added without changing the loader.

Manual V1 uses `analyze_competitor.md`, `generate_names.md`, and
`generate_package_v1.md`. Prompts are copied by users, not sent to an API by the
manual services. Competitor inputs are text only; URLs are references, not retrieved
pages or images. Require explicit uncertainty and avoid copying competitor branding.

`generate_package.md` retains the legacy Phase 2 schema for regression compatibility.
It is not the manual V1 package template. Each legacy template has a task marker
used by the offline mock provider. Python schema validation is mandatory regardless
of what the prompt instructs; no automatic repair of imported JSON is permitted.
