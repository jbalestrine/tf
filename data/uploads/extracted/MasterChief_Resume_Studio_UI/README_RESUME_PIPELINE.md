# Resume-as-Code Pipeline (MasterChief Module)

Automated multi-format resume generator driven by a **Single Source of Truth (`resume.yaml`)**.

## Repository Layout
```text
├── resume.yaml                        # Single Source of Truth (pre-loaded with Master v2 data)
├── build_resumes.py                   # Python build engine (renders DOCX + PDF outputs)
├── template_v2.html                   # Jinja2 + CSS template for Dark-Header Architect PDF
├── .github/workflows/build-resume.yml # GitHub Actions CI/CD workflow
└── dist/                              # Auto-generated output folder
    ├── Joseph_Balestrine_DevOps_Architect_Master.docx
    ├── Joseph_Balestrine_Executive_2Page.docx
    ├── Joseph_Balestrine_Slide_Edition.docx
    ├── Joseph_Balestrine_Cover_Letter.docx
    └── Joseph_Balestrine_Architect_Portfolio.pdf
```

## How Tier Filtering Works
Every skill group, job role, and bullet in `resume.yaml` includes a `tiers` array:
- `master` — Included in the full ATS Master `.docx`
- `exec` — Included in the condensed 2-Page Executive `.docx`
- `slideedition` — Included in the Slide Edition `.docx`
- `pdf` — Included in the Dark-Header Visual Architect `.pdf`

Edit `resume.yaml` once and run `python build_resumes.py` to generate all five artifacts.
All three resume DOCX tiers include editable text in a four-column metric strip
and a two-column competency table, with Azure blueprint-style role cards and a
timeline.
ATS systems vary in how they read tables, so verify extraction in the target system;
the layout cannot guarantee compatibility with every ATS.
The DOCX preview and ReportLab PDF share the navy, cyan, and Azure palette.
Rebuild existing artifacts to apply the updated styles.

## Build Targets
Run `python build_resumes.py --target <target>` with one of `all`, `master`, `exec`,
`slideedition`, `coverletter`, `interviewprep`, or `pdf`. The default target is `all`.

The interview-prep DOCX uses the first four metrics and the `interview_prep`
section. Its compact layout is intended for one page; actual pagination depends
on the Word renderer, fonts, and the length of edited content.

Cover-letter builds accept `--company <name>` and `--role <title>`; those values replace
`{company_name}` and `{role_title}` in the `cover_letter` section of `resume.yaml`.

PDF generation uses ReportLab and the SVG brand emblem from `template_v2.html`;
it does not require GTK, Pango, or a browser binary. The PDF uses a paginated
ReportLab layout based on the same resume data and branding, rather than rendering
the live HTML preview pixel-for-pixel.
