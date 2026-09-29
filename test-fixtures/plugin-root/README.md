# Plugin root

The pipeline skill resolves the plugin's own folder with one Bash call, under
"Before stage 3" in `skills/second-brain-pipeline/SKILL.md`; the topic
deep-dive skill runs the same call. It cannot be a script in the plugin, since
finding the plugin's scripts is its job. This check extracts that block from
the skill and runs it against throwaway layouts, with `HOME` pointed at each.
From the repo root:

```
awk '/^## Before stage 3/{s=1} s && /^```bash/{p=1; next} p && /^```/{exit} p' \
  skills/second-brain-pipeline/SKILL.md > "$T/resolve.sh"
mk() { mkdir -p "$1/.claude-plugin" "$1/templates" "$1/scripts"; echo "{\"name\": \"$2\"}" > "$1/.claude-plugin/plugin.json"; }
root() { (cd "$1" && env -u CLAUDE_PLUGIN_ROOT -u CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS HOME="$2" "${@:3}" bash "$T/resolve.sh"); }
P=.claude/plugins
mkdir -p "$T/proj/scripts" "$T/proj/templates"; mk "$T/home1/$P/marketplaces/arxiv-mcp" arxiv-mcp-server
root "$PWD" "$T/home1"                                   # plugin root: <this repo>; wave size: 20
root "$T/proj" "$T/home1"                                # plugin root: NOT FOUND
root "$T/proj" "$T/home1" CLAUDE_PLUGIN_ROOT="$PWD"      # plugin root: <this repo>
mk "$T/home2/$P/cache/sbr/second-brain-researcher/0.1.0" second-brain-researcher
mk "$T/home2/$P/marketplaces/second-brain-researcher" second-brain-researcher
root "$T/proj" "$T/home2"                                # plugin root: …/marketplaces/second-brain-researcher
echo "{\"plugins\": {\"second-brain-researcher@sbr\": [{\"installPath\": \"$T/home2/$P/cache/sbr/second-brain-researcher/0.1.0\"}]}}" \
  > "$T/home2/$P/installed_plugins.json"
root "$T/proj" "$T/home2"                                # plugin root: …/cache/sbr/second-brain-researcher/0.1.0
```

`bash test-fixtures/run_offline.sh plugin-root` runs the commands above,
`$T` a temp dir; change the README and the runner together.

What each tests:

- the working directory, when it is this repo (development with
  `claude --plugin-dir .`), and the default wave size;
- a researcher's project that has its own `scripts/` and `templates/` is not
  the plugin, and neither is another plugin's marketplace;
- `$CLAUDE_PLUGIN_ROOT` wins when it is set;
- without an install record, a marketplace clone of this plugin is used;
- the installed copy (`installPath` in `installed_plugins.json`) is preferred
  to the marketplace clone, which can be a different version than the agents
  that are running.
