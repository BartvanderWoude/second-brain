# Schema copies

`templates/research-problem-profile-format-spec.md` defines the profile. The
intake skill keeps one sanctioned copy of its fields, the YAML skeletons in
`skills/research-problem-intake/SKILL.md` and `deep-dive.md`, because reading
the whole spec in the main conversation would cost more than the copy. This
check fails when the two field sets drift apart. From the repo root:

```
fields_spec() { grep -oE '^\| `[a-z_]+`' templates/research-problem-profile-format-spec.md | tr -d '|` ' | sort -u; }
fields_intake() { awk '/^ *```yaml/{p=1;next} /^ *```/{p=0} p' skills/research-problem-intake/SKILL.md \
    skills/research-problem-intake/deep-dive.md | grep -oE '^ *[a-z_]+:' | tr -d ' :' | sort -u; }
diff <(fields_intake) <(fields_spec)
```

`bash test-fixtures/run_offline.sh schema-copies` runs the commands above; change the README and the runner together.

No output means it passes: every field in the spec's schema table appears in
an intake skeleton, and the skeletons hold no field the table lacks. A field
added to one without the other shows up in the diff.
