# Interactive paragraph comparison

After running compare_paragraphs.py and setting up the glyph browser:

```bash
work="$HOME/Cykat-recovery/IMPACT-GT-detailed"
python3 glyph-browser/prepare_comparison_report.py \
  "$work/PSNC_POLISH_ANTIQUA_GT.ZIP" \
  "$work/PSNC_POLISH_GOTHIC_GT.ZIP" \
  --paragraphs "$HOME/git/groundtruth-pol" \
  --comparison "$work/paragraph-comparison" \
  --data "$work/glyph-browser-data"
```

Open http://127.0.0.1:8081/comparison/ using the existing static local server.
If it is not running, start it as in BROWSER.md. No extra dependencies are
required. The generator reuses existing diff segments and obtains region
bounding rectangles from source PAGE, verifying the recorded transcriptions
and dimensions. It writes only the comparison subdirectory in the local
generated browser data. Re-running replaces these generated report files.

Select a directional change pair (all pairs, not only the top 30); select a
single edit occurrence to see both complete region transcriptions, with the
selected edit emphasized. Empty segments are displayed as ∅, spaces as ␠ in
the pair table. All texts retain original Unicode code points. The report
also exposes unmatched regions, geometry-only differences, and unmatched
pages. The scan viewer marks region bounding rectangles, not polygons or
individual characters; source rectangle overlap is possible. No automatic
judgment of which transcription is correct. Diff segments are the existing
SequenceMatcher output, not uniquely determined character correspondences.

Keep the report local, since it contains original detailed transcriptions.
Report source is tracked, not generated data. Full local corpus testing is
still required.
