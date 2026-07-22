These fixture HTML files are hand-built to match the *documented* structure
(table columns, header labels, hyperlink query params) inferred from the
Tuesday Night League's rendered pages, not saved from the real site — this
tool never had access to raw HTML, only a pre-rendered text view of it, so
there was nothing byte-for-byte real to save.

They exist to catch Python bugs (crashes, off-by-one slicing, wrong dict
keys) before you ever hit the live site, not to prove the real markup
matches. Run `ggscrape --dump-html ./dump <base_url> ...` once against the
real site and swap these fixtures for the real saved pages to get a test
suite that actually proves something.
