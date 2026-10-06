# Structured prompt assets

UTF-8 Markdown templates loaded by `core.prompts.PromptLoader`. Render `${name}`
variables with `PromptRenderer`; use `$$` for a literal dollar. JSON braces and
future title slots such as `{artist}` do not require escaping. Inserted input is
not recursively rendered. Missing files, invalid UTF-8, syntax, or variables raise
`PromptError`. New prompts can be added without changing the loader.

Each template starts with an exact task marker used by the offline mock provider.
These are executable structured prompts, replacing the Phase 1 placeholders.
All AI responses must pass the matching model's `from_ai_dict` factory; prompt
instructions alone never establish validity.
