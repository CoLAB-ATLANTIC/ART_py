# ART presentation

`art_overview.qmd` is a Quarto Reveal.js slide deck describing the current local ART implementation.
It includes execution diagrams, YAML examples, speaker notes, consolidation logic, and current limitations.
`art_slides.scss` supplies its theme. No Python examples or external model programs execute during rendering.

From the repository root, with Quarto installed:

```bash
quarto render docs/art_overview.qmd
```

The output is `docs/art_overview.html`. Resources are embedded for sharing as one HTML file.
For live preview:

```bash
quarto preview docs/art_overview.qmd
```

Use the arrow keys to navigate, `Esc` for the slide overview, and `S` for the presenter view with notes.
The configuration snippets use illustrative paths; adapt them to an existing project before running ART.

The slides were checked against `src/art.py`, `src/common/model_base.py`, `src/common/trigger.py`, both processing
modules, and `src/mohid/mohid_water.py`. Implementation details take precedence over older documentation.
