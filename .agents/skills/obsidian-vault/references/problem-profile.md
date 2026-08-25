# Problem profile contract

The intake stage supplies one Markdown file with YAML frontmatter and a free-text body. `id` is the stable graph key. The body is human-readable and is not a fallback source for missing structured fields.

Required frontmatter:

```yaml
id: <stable-id>
created: <yyyy-mm-dd>
status: draft | confirmed
domain:
data_modality:
cohort_description:
task:
reference_standard:
current_approach:
observed_failure_mode:
close_field_terms: []
generalized_methodology_terms: []
cross_project_linking: false
```

Optional frontmatter:

```yaml
study_design:
data_source:
inclusion_exclusion_criteria:
data_partitioning:
sample_size:
related_projects: []
```

Discovery may only consume a `confirmed` profile. Vault creation may preserve a `draft` profile but must report its status.

