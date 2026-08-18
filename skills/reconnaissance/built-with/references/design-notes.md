# Dossier design notes

The dossier is the human-facing deliverable: a plain-English map of the target's
third-party stack that a fresh reader (a client, an exec, a security reviewer)
can scan without knowing anything going in. `assets/template.html` supplies the styled shell (fonts, palette, print rules);
the generator injects the header, tables, and appendices into it.

## The reader's four questions
Every vendor row answers, in this column order:
1. **What they use** - the vendor name + a two-word role label.
2. **What it's for** - plain English. This is the ONLY column that is your
   interpretation; everything else is copied evidence.
3. **How sure** - a confidence chip: Confirmed / High / Likely.
4. **Prove it** - the exact endpoint, header, or on-screen string, verbatim.

## Provenance rule (say which is which)
Readers must be able to tell evidence from analysis at a glance:
- **"Quotation marks + italic"** = the target's own on-screen text, copied
  word-for-word from their bundle. Never paraphrase inside quotes.
- **`monospace`** = their exact endpoint path / header / config token.
- The **What it's for** column is your reading - state it plainly, no quotes.
State this rule near the top of the dossier so nobody has to guess.

## Confidence levels
- **Confirmed** - live API call or UI string in the bundle, or proven by a
  response header. (Most rows.)
- **High** - not branded, but the fingerprints fit exactly one vendor and
  nothing competes (e.g. a distinctive custom request header that only one vendor sets).
- **Likely** - referenced in code but the smoking-gun key/call wasn't pulled.

## Categories (the three uses)
- **Customer-connected** (teal edge) - the customer wires it up; part of the
  product. Sales & security-review surface.
- **Behind-the-scenes** (indigo edge) - powers a feature, invisible to the
  customer. Vendor-dependency & data-processing surface.
- **Internal** (grey edge) - hosting, monitoring, analytics. Runs the company,
  not the feature.
Category is a judgement call - a hostname alone rarely settles product vs ops.
Use the CSP, the endpoint the vendor's ID rides on, and the UI copy to decide.

## Layout that survives print
- **Landscape Letter** (`@page{size:letter landscape}`) for the wide four-column
  table. Portrait is fine too, but then the four columns don't fit and it reads
  best as stacked cards - pick per user preference.
- **Chrome's print viewport is fixed and narrow (~750 CSS px) no matter the paper
  size.** It lays out at that width and then *scales the vector output* to fill
  the page - so a bigger `@page` does NOT give you more CSS width. Verified: a
  4in, 14in, and 24in page all report the same `<1000px` media-query width. The
  practical consequence: you cannot get the wide table just by switching to
  landscape - at ~750px the on-screen mobile breakpoint stacks it. You must
  **re-assert the four-column grid inside `@media print`** and fit the columns to
  ~750px (tighten widths, drop base font to ~12px); Chrome scales that up to fill
  the landscape page and it looks spacious. When you re-assert the grid, also
  reset every per-cell `grid-column`/`grid-row` the mobile block pinned, or the
  cells land in the wrong columns (the status chip ends up under "what it's for").
  The template's `@media print` block is the working reference.
- To verify a table page (qlmanage only thumbnails page 1), mirror the
  `@media print` rules under `@media screen`, screenshot the HTML at ~745px wide,
  and read that - it matches the printed result.
- **One card per vendor**, separated by real whitespace (a flex `gap`), each with
  a category-colored 4px left edge and a thin full border. No drop-shadow - in
  print a soft shadow renders as a grey halo that makes cards look connected.
- **No internal horizontal dividers** inside a card beyond a single rule under
  the vendor-name header; extra rules read like table-row separators and blur
  the card boundaries.
- `print-color-adjust: exact` so chips and colored edges actually print.
- Force the light palette for print; give `body` an explicit background.

## Theme-aware, self-contained
The template is theme-aware (light + dark tokens) and fully self-contained
(Google Fonts is the only external load). Keep it that way so it works as a
claude.ai Artifact and prints cleanly.
