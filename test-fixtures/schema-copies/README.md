# Schema copies

`templates/research-problem-profile-format-spec.md` defines the profile. Two
skills keep sanctioned copies of its fields, as YAML skeletons, because reading
the whole spec in the main conversation would cost more than the copy: the
intake skill (`skills/research-problem-intake/SKILL.md` and `deep-dive.md`)
and the causal-graph skill (`skills/second-brain-causal-graph/SKILL.md`),
which writes causal profiles with its own Q&A. This check fails when the
skeletons' fields and the spec's drift apart. From the repo root:

```
fields_spec() { awk -F' *[|] *' '/^[|] `[a-z_]+`/ {print $2}' \
    templates/research-problem-profile-format-spec.md | tr -d '`' | sort -u; }
fields_intake() { awk '/^ *```yaml/{p=1;next} /^ *```/{p=0} p' skills/research-problem-intake/SKILL.md \
    skills/research-problem-intake/deep-dive.md skills/second-brain-causal-graph/SKILL.md \
    | grep -oE '^ *[a-z_]+:' | tr -d ' :' | sort -u; }
diff <(fields_intake) <(fields_spec)
```

`bash test-fixtures/run_offline.sh schema-copies` runs the commands above; change the README and the runner together.

No output means it passes: every field in the spec's schema table appears in
one of the skeletons, and the skeletons together hold no field the table
lacks. A field added to one without the other shows up in the diff. The
causal fields (Required `causal`) are covered by the causal-graph skill's
skeleton alone.
