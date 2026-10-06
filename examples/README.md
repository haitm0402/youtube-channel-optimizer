# Manual workflow examples

All files are UTF-8. Start `python app.py --manual --input-json examples/competitor_input.json`.
When requested, copy the contents of `analysis_response.json`, then type `END_JSON`
on its own line. Repeat with `names_response.json`, select `Mây Âm Nhạc`, then paste
`package_v1_response.json` and finish with `END_JSON`.

These are illustrative, offline responses, not results fetched from the reference
URL. They allow testing the manual bridge without an AI account or provider.
For real work, copy the app's prompt to ChatGPT/Codex yourself and paste its JSON
response back. Validate and review each result. No avatar input or image prompts
are included in the active V1 package.
