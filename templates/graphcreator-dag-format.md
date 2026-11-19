# The GraphCreator file format

GraphCreator saves a causal DAG (directed acyclic graph) as a YAML file named `<name>.dag.yaml`. This document describes that file for programs that read it, such as a tool that generates synthetic data sets from DAGs. It covers the format `graphcreator/0.1`.

A file describes:

- the **variables** (nodes): their name, role, type, levels, unit, description and position on the canvas;
- the **arrows** (edges): which variable causes which, with evidence and a note;
- optional **simulation details**: how common each level of a variable is (shares), how a variable's causes combine (form), whether an arrow raises or lowers its effect (sign) and how strong the effect is (strength).

Every field except `schema` and the names is optional. A reader should not expect any simulation detail to be present, and should fall back to its own defaults where one is missing.

## Example

```yaml
schema: graphcreator/0.1
name: Surgical site infection
nodes:
  - name: Diabetes
    var_type: categorical
    levels: ["no", "yes"]
    shares: [0.88, 0.12]
    pos: [0, 0]
  - name: Wound class
    var_type: categorical
    levels: [clean, clean-contaminated, contaminated]
    shares: [0.6, 0.3, 0.1]
    form: threshold
    pos: [0, 160]
  - name: SSI
    role: outcome
    var_type: categorical
    levels: ["no", "yes"]
    shares: [0.92, 0.08]
    form: linear
    pos: [300, 80]
edges:
  - from: Diabetes
    to: SSI
    sign: positive
    strength: medium
  - from: Diabetes
    to: Wound class
    sign: {clean: negative, contaminated: positive}
    strength: small
  - from: Wound class
    to: SSI
    sign: {clean: negative, clean-contaminated: positive, contaminated: positive}
    strength: large
```

In words:

- 12% of patients have diabetes, 10% of wounds are contaminated, and 8% of patients get a surgical site infection (SSI).
- Diabetes raises the risk of SSI, with a medium effect.
- Diabetes makes a clean wound less likely and a contaminated wound more likely, with a small effect. It says nothing about clean-contaminated wounds.
- Compared with a clean wound (the first level), clean-contaminated and contaminated wounds both raise the risk of SSI, with a large effect.
- The wound class depends on its cause through cut-offs (`threshold`), and the effects of SSI's causes add up in straight lines (`linear`).

`no` and `yes` are in quotes because YAML 1.1 readers would otherwise read them as `false` and `true` (see [Text and YAML 1.1](#text-and-yaml-11)).

## The file

The file is UTF-8 text in YAML. Its top level is a map with these keys, in this order:

| Key | Type | Required | Meaning |
|---|---|---|---|
| `schema` | text | yes | The format and its version: `graphcreator/0.1`. |
| `name` | text | no | The graph's title. |
| `locked` | true | no | An editor setting: GraphCreator does not let people change the graph. It has no causal or simulation meaning; readers can ignore it. Written only when the graph is locked. |
| `nodes` | list of nodes | no | The variables. Missing means none. GraphCreator always writes it, as `[]` when empty. |
| `edges` | list of edges | no | The arrows. Missing means none. GraphCreator always writes it, as `[]` when empty. |

GraphCreator refuses a file with a key it does not know, at any level, so a file it accepts has only the keys listed in this document.

### Nodes

Each item of `nodes` is a map with these keys, written in this order:

| Key | Type | Required | Meaning |
|---|---|---|---|
| `name` | text | yes | The variable's name. Unique and not empty. |
| `role` | `exposure`, `outcome`, `latent`, `adjusted`, `selected` or `other` | no | The part the variable plays in the causal question. Missing means `other`. |
| `var_type` | `categorical`, `ordinal`, `continuous` or `discrete` | no | How the variable is measured. Missing means the type is not known. |
| `levels` | list of text | no | The values of a categorical or ordinal variable, in order. Only with those two types. |
| `shares` | list of numbers | no | How common each level is, in level order. Only with `levels`. |
| `description` | text | no | What the variable is, in words. |
| `unit` | text | no | The unit of a continuous or discrete variable, such as `g` or `years`. Only with those two types. |
| `form` | `linear`, `smooth` or `threshold` | no | How the variable's causes combine. |
| `pos` | `[x, y]`, two numbers | no | The position on GraphCreator's canvas. |

### Edges

Each item of `edges` is a map with these keys, written in this order:

| Key | Type | Required | Meaning |
|---|---|---|---|
| `from` | text | yes | The name of the cause. |
| `to` | text | yes | The name of the effect. |
| `sign` | `positive` or `negative`, or a map from level names to `positive` or `negative` | no | Whether the cause raises or lowers the effect. |
| `strength` | `small`, `medium` or `large` | no | How large the effect is, whatever its sign. |
| `evidence` | list of text | no | References that support the arrow, such as `PMID:123` or `doi:10.1000/xyz`. Missing means none. |
| `note` | text | no | Why the arrow was drawn, or what is uncertain about it. |

### What a valid file guarantees

GraphCreator refuses to open a file that breaks one of these rules, and never saves one:

- Every node has a name, and no two nodes share a name. Names are compared exactly, after removing spaces at the start and end: `Age` and `age` are two different nodes.
- `from` and `to` name existing nodes.
- No edge points from a node to itself, no edge appears twice, and the edges form no directed cycle.
- `levels` appear only on categorical and ordinal nodes, and `unit` only on continuous and discrete nodes.
- `shares` appear only on nodes with `levels`, have exactly one number per level, and every number is 0 or more.

Other problems are only warnings in GraphCreator, so a saved file can contain them. A reader should cope with them (see [Reading rules](#reading-rules)):

- a node without a type;
- a categorical or ordinal node with fewer than two levels, or with the same level twice;
- shares that do not add up to 1;
- a form on a node without causes;
- a sign that does not fit the types of the edge's two ends, or that names a level the node does not have.

Text fields that are empty are left out of the file, as are `role: other`, empty `evidence` and an empty sign map.

## Meaning

### Roles

The role is the part a variable plays in the causal question the DAG was drawn for:

| Role | Meaning |
|---|---|
| `exposure` | The cause whose effect is to be estimated. |
| `outcome` | The effect to be estimated. |
| `latent` | A variable that was not or cannot be measured. |
| `adjusted` | A variable controlled for in the analysis, by stratifying or adding it to the model. |
| `selected` | A variable the study population was selected on, such as hospital admission. |
| `other` | Any other variable in the model. |

A node has exactly one role. Any number of nodes may be exposures or outcomes.

### Types and levels

| Type | Meaning | Extra fields |
|---|---|---|
| `categorical` | Values are categories without an order, such as blood group. A yes/no variable is categorical with two levels. | `levels`, `shares` |
| `ordinal` | Values are ordered categories, such as low, mid and high. | `levels`, `shares` |
| `continuous` | Values are measured numbers, such as weight. | `unit` |
| `discrete` | Values are whole numbers, such as a count. | `unit` |

The order of `levels` matters for both categorical and ordinal variables:

- For an ordinal variable, the levels go from lowest to highest.
- For an ordinal variable, and for a variable with levels on the effect side of an edge, a later level counts as higher when a sign is read (see [Sign](#sign)). For a variable with levels `["no", "yes"]`, "yes" is higher.
- For a categorical cause, every level carries its own sign, the first level included. There is no reference level.

Two words for the two sides of an edge:

- A categorical variable with three or more levels is called **nominal**. An ordinal variable is never nominal, because its levels are ordered. The **effect** side uses this word: an effect's levels are alternatives whose chances add up to 1, so an effect with two levels needs only one sign (if "yes" becomes more likely, "no" becomes less likely).
- A categorical variable with two or more levels **has levels for signs**. The **cause** side uses this: a cause's levels are not alternatives in one sum, so each of them has its own answer to "does being in this level raise or lower the effect?".

### Shares

`shares` are the proportions of a variable's levels in the population, in level order. `levels: ["no", "yes"]` with `shares: [0.88, 0.12]` means 12% "yes".

- On a node without causes, they are the variable's distribution.
- On a node with causes, they are the overall proportions the simulation should aim for, for example by choosing intercepts or thresholds: "SSI occurs in 8%".
- Shares should add up to 1. GraphCreator warns when they are off by more than 0.001, but still saves them.

### Form

`form` says how a node's causes combine:

| Form | Meaning |
|---|---|
| `linear` | Effects add up in straight lines. |
| `smooth` | Effects curve: they can grow, level off or bend. A neural-network mechanism fits here. |
| `threshold` | Effects switch at cut-offs, such as a risk that jumps above an age. A tree mechanism fits here. |

The form does not describe noise; that is left to the simulator. A form on a node without causes means nothing.

### Strength

`strength` is the size of an edge's effect, whatever its sign. The bands have names, not numbers. As guidance, on a standardised scale (a standardised coefficient or something comparable):

| Strength | Standardised effect |
|---|---|
| `small` | about 0.1 to 0.3 |
| `medium` | about 0.3 to 0.6 |
| `large` | about 0.6 to 1.0 |

A reader may use other numbers, but these are the shared default. With a sign per level, the strength applies to each signed level.

### Sign

`sign` says whether a cause raises or lowers its effect. What it looks like depends on the two ends, in this order:

| Cause (`from`) | Effect (`to`) | Sign | Meaning |
|---|---|---|---|
| nominal | nominal | none | A sign is not available, because a level-by-level table would be needed. Strength is still allowed. |
| any | nominal | a map from the effect's levels to words | `positive`: a higher cause, or being in that level of the cause, makes that level of the effect more likely. `negative`: less likely. Levels left out are not specified. |
| has levels for signs | not nominal | a map from **all** the cause's levels to words | `B: positive` means that being in level B gives a higher effect than the average over the cause's levels; `negative` a lower one. There is no reference level. Levels left out are not specified. |
| no levels for signs | not nominal | one word | `positive`: a higher cause gives a higher effect. `negative`: a higher cause gives a lower effect. |

- "Higher" follows the level order for an ordinal variable and for a leveled effect, and the value for continuous and discrete ones. An untyped variable is neither nominal nor leveled for signs.
- **Any combination of signs is allowed** on a map over a cause's levels, every level `positive` included. The file may describe a sample that is not a representative population sample, so GraphCreator does not restrict or warn about the combination. If your model needs the level effects to cancel out, centre them yourself (for example by subtracting their share-weighted mean).
- **One word instead of a map** on an edge whose cause has exactly two levels means a sign on the **second** level, the first unspecified: `positive` reads as "yes raises the effect". Files written before per-level signs use this form, and it keeps its meaning. With three or more levels a word does not fit; treat it as missing.

In the example:

- `Diabetes → SSI`: the cause has two levels and a word, so it signs the second level. `positive`: having diabetes ("yes") raises the chance of SSI ("yes"); the "no" level is not specified.
- `Diabetes → Wound class`: the effect is nominal, so a map over the effect's levels. Diabetes makes `clean` less likely and `contaminated` more likely; `clean-contaminated` is not specified.
- `Wound class → SSI`: the cause has levels for signs and the effect is not nominal, so a map over all the cause's levels. Compared with the average wound class, a `clean` wound lowers the chance of SSI, and `clean-contaminated` and `contaminated` wounds raise it.

A sign map is written in flow style, with its keys in the order of the levels they name.

`sign` and `strength` are independent: an edge can have either, both or neither.

### Description, unit, evidence and note

`description`, `unit`, `evidence` and `note` document the model for people. They carry no simulation meaning, though a unit can help to label generated columns.

### Position

`pos: [x, y]` is where the node is drawn in GraphCreator, in canvas pixels, with y growing downward. It is the top-left corner of the box around the node's circle, and is written as whole numbers. It has no causal or simulation meaning. When a node has no position, GraphCreator lays out the whole graph when it opens the file.

## Reading rules

A reader that generates data from a file should follow these rules, so that every reader understands a file the same way:

- **Check `schema`.** It must be `graphcreator/0.1`.
- **Use names as given.** A name is any text, such as `Kidney disease` or `BMI (kg/m²)`. Use it as it is, or derive your own identifiers from it; do not expect it to be a valid variable name in R or Python.
- **Sort the nodes yourself.** The order of `nodes` is the order in which they were drawn, not a topological order. Sort them by the edges before generating data (for example with Python's `graphlib.TopologicalSorter`).
- **Level order is meaningful.** The position of a level in `levels` is its class index (0 for the first level), and it defines which level counts as higher for signs.
- **A sign map over a cause's levels has no reference level.** Each sign is read against the average over that cause's levels, and the first level is an ordinary key. A map written before per-level signs may have no key for the first level; that level is then simply unspecified.
- **Normalise shares.** Divide each share by their sum. Read them as decimal numbers: a share of `1` is written without a decimal point. When the sum is 0, treat the shares as missing.
- **Ignore sign-map keys that are not levels** of the node the map is about.
- **Treat a sign that does not fit the edge as missing:** a map where a word is expected, any sign between two nominal nodes, or a word where a map is expected — except the one-word form on a cause with exactly two levels, which signs that cause's second level. GraphCreator warns about each of the others.
- **Map the roles to your own concepts.** For example, `outcome` can become the target column and `latent` a hidden variable that is generated but not included in the output. `exposure`, `adjusted`, `selected` and `other` describe the causal question and carry no simulation meaning.
- **Fill in what is missing.** Every simulation detail is optional. A node without a type, shares or form, and an edge without a sign or strength, leave the choice to the reader.

## Text and YAML 1.1

GraphCreator writes YAML 1.2. Many YAML readers, including Python's PyYAML, read YAML 1.1, where some plain words are not text: `yes`, `no`, `on` and `off` are booleans, `~` is null, and `1_000` is a number.

So that every reader sees the same text, GraphCreator writes any text in double quotes when a YAML 1.1 reader would read it as something else:

- booleans and null: `yes`, `no`, `on`, `off`, `y`, `n`, `true`, `false`, `null` and `~`, in lower case, Capitalised or UPPER case;
- numbers in YAML 1.1 forms, such as `1_000`, `0x1F`, `0o17`, `1:30`, `.inf` and `.nan`;
- dates, such as `2024-01-31`.

This applies to every text in the file: names, `from` and `to`, levels, sign-map keys, descriptions, units, evidence and notes. Text that YAML 1.2 already requires to be quoted is quoted as well, and evidence items are always quoted. For example, a node with levels `no` and `yes` is written `levels: ["no", "yes"]`, and PyYAML reads it as `['no', 'yes']`.

A file written by hand or by another program may not follow this. A reader that accepts such files should check that names and levels are text.

## Reading a file in Python

This example uses PyYAML (`pip install pyyaml`). It reads the file, finds the shape of each sign, normalises the shares and sorts the nodes.

```python
from graphlib import TopologicalSorter

import yaml

with open("surgical-site-infection.dag.yaml", encoding="utf-8") as f:
    graph = yaml.safe_load(f)

if graph.get("schema") != "graphcreator/0.1":
    raise ValueError("not a GraphCreator 0.1 file")

nodes = {node["name"]: node for node in graph.get("nodes") or []}
edges = graph.get("edges") or []


def is_nominal(node):
    return node.get("var_type") == "categorical" and len(node.get("levels", [])) >= 3


def has_classes(node):
    return node.get("var_type") == "categorical" and len(node.get("levels", [])) >= 2


def shares(node):
    values = [float(s) for s in node.get("shares", [])]
    total = sum(values)
    return [s / total for s in values] if total > 0 else None


def sign(edge):
    """One sign, or a dict from levels to signs, or None."""
    cause, effect = nodes[edge["from"]], nodes[edge["to"]]
    value = edge.get("sign")
    if is_nominal(cause) and is_nominal(effect):
        return None
    if is_nominal(effect):
        levels = effect["levels"]
    elif has_classes(cause):
        levels = cause["levels"]
        if isinstance(value, str):
            # One word on a two-level cause signs its second level.
            return {levels[1]: value} if len(levels) == 2 else None
    else:
        return value if isinstance(value, str) else None
    if not isinstance(value, dict):
        return None
    return {level: s for level, s in value.items() if level in levels}


parents = {name: [] for name in nodes}
for edge in edges:
    parents[edge["to"]].append(edge["from"])
order = list(TopologicalSorter(parents).static_order())

for name in order:
    node = nodes[name]
    print(name, node.get("var_type"), node.get("levels"), shares(node), node.get("form"))
for edge in edges:
    print(edge["from"], "->", edge["to"], sign(edge), edge.get("strength"))
```

For the example file it prints:

```text
Diabetes categorical ['no', 'yes'] [0.88, 0.12] None
Wound class categorical ['clean', 'clean-contaminated', 'contaminated'] [0.6, 0.3, 0.1] threshold
SSI categorical ['no', 'yes'] [0.92, 0.08] linear
Diabetes -> SSI positive medium
Diabetes -> Wound class {'clean': 'negative', 'contaminated': 'positive'} small
Wound class -> SSI {'clean-contaminated': 'positive', 'contaminated': 'positive'} large
```
