# Channel Profile Manager

Channel Profile Manager stores reusable **channel DNA** separately from one optimization
project. It is designed for operating many music channels without retyping artist,
market, language, music, vocal, lyric, Suno, branding and SEO rules every time.

Launch the existing desktop application:

```powershell
py -3 app.py --gui
```

Use **CHANNEL PROFILES** in the header to create, open, edit, archive, restore, copy,
or export profiles. Runtime records are stored under:

```text
data/channel_profiles/<UUID>.json
```

They are independent from `data/sessions/`.

A profile can contain:

- channel name, artist direction, market, language and upload time
- positioning, description and slogan
- niche, genre and subgenre
- vocal direction, flow direction, lyric rules and Suno style rules
- visual identity, thumbnail rules and banner direction
- SEO topics, channel keywords, video keywords, default tags and hashtags
- reusable title templates, competitor URLs and internal notes

A completed optimizer project can be converted with **SAVE AS CHANNEL PROFILE**.
The operation is idempotent per source session: pressing it again opens/reuses the
same profile rather than creating duplicates.

**COPY PROFILE JSON** produces a portable `channel_dna_v1` payload without local
UUID/revision metadata. **EXPORT JSON** writes the same reusable payload under
`exports/channel_profiles/` without overwriting an existing export. This portable
shape is intended to become the input contract for a future AI Music Song Factory.

Archiving never deletes the JSON file. Archived profiles are read-only and can be
restored from the Channel Profiles screen.
