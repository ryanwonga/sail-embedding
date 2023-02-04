# SAIL Syntax Trees

The goal is to create syntax trees given an XML representation of a SAIL expressionable object 
(e.g., expression rules, interfaces). 

Because of the hierarchical nature of functions and values in SAIL, we can easily build syntax trees.

For example, given this SAIL expression:
```SAIL
a!toJson(
  {
    logSelected: ri!logSelected,
    breadcrumbs: concat(ri!bread, "crumbs"),
    filterMeasure: "Measure",
  }
)
```

This will be represented by syntax trees as:
```mermaid
graph TD
    node1("a!toJson(function)")
    node2("undefined_parameter1(parameter)")
    node3("variant1(function)")
    node4("logSelected(parameter)")
    node5("ri!logSelected(rule_input)")
    node6("breadcrumbs(parameter)")
    node7("concat(function)")
    node8("undefined_parameter2(parameter)")
    node9("ri!bread(rule_input)")
    node10("undefined_parameter3(parameter)")
    node11("crumbs(text)")
    node12("fitlerMeasure(parameter)")
    node13("Measure(text)")

    node1-->node2
    node2-->node3
    node3-->node4
    node3-->node6
    node3-->node12
    node4-->node5
    node6-->node7
    node7-->node8
    node7-->node10
    node8-->node9
    node10-->node11
    node12-->node13
```
Where each node contains the object's name and type. Possible types are `function`, `parameter`,
`comment`, `text`, `local variable`, `rule input`, and `function variable`.

# Usage
Pass a valid XML path to `get_syntax_tree_from_xml(xml_path: Path)` or a SAIL expression to 
`get_syntax_tree_from_sail(sail: str)`. See usage at the bottom of `syntax_tree_parsers.py`.

Returns:
1. root_object: `SailObject` type with properties
   1. name: name of object
   2. object_type: type of object
   3. line: where in the code the object was retrieved from
   4. values: list of `SailObject` objects that are the children of the object
2. names_map: `dict` type where the keys are the object names. This can be useful to get the 
values of common object names like "label", "placeholder", or "stampIcon".