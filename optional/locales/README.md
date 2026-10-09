# Installer locales

The installer's own prompts. Nothing here affects an installed project — the kit's
documents are English, and a project's *own* languages are declared in its charter
(`Languages & localisation`) instead.

`install.py` ships English inline. `--lang <code>` loads `<code>.json` from this directory
and overrides the strings it contains; anything missing stays English, so a partial
catalogue is usable rather than broken.

## Adding one

Copy the keys you want from the `EN` dictionary at the top of `install.py` into
`<code>.json`:

```json
{
  "q.dest": "Hangi proje dizinine kurulsun?",
  "q.name": "Proje adı"
}
```

Then run:

```sh
./install.sh /path/to/project --lang tr
```

Rules that keep a catalogue safe to load:

- Keep every `{placeholder}` that appears in the English string, spelled the same. A
  missing one is ignored; an invented one falls back to English for that string.
- Keep answer keys English. `y`, `n`, `b`, `s`, `S`, `q` and `?` are what the installer
  reads from the keyboard, and translating the *prompt* is enough — do not promise a
  keystroke the code does not accept.
- Line length matters: prompts print inside a two-space indent on an 80-column terminal.

No locale is shipped with the kit yet, so there is nothing here to copy from — only this
file and the English source in `install.py`.
