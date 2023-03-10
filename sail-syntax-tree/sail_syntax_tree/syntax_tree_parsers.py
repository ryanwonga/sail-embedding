import uuid
from enum import Enum
from pathlib import Path
import re
from typing import List, Tuple, Dict

TYPE_CONSTRUCTOR_STARTS_WITH = "'type!{"


class ObjectType(str, Enum):
    FUNCTION = "function"
    PARAMETER = "parameter"
    COMMENT = "comment"
    TEXT = "text"
    LOCAL = "local variable"
    RI = "rule input"
    FV = "function variable"
    INDEX = "index"


class SailObject:
    def __init__(self, object_name: str, object_type: ObjectType, line: int, value=None):
        if value is None:
            value = []
        self.name = object_name
        self.object_type = object_type
        self.line = line
        self.values = value

    def add_value(self, value: 'SailObject'):
        self.values.append(value)

    def get_print(self):
        return f"name: {self.name}, objectType: {self.object_type}, line: {self.line}, " \
               f"size of values: {len(self.values)}"


class States:
    def __init__(self):
        self.is_quote = False
        self.is_single_quote = False
        self.is_comment = False
        self.is_type_constructor = False
        self.is_function_name = False


def get_syntax_tree_from_xml(xml_path):
    sail = get_sail_expression(xml_path)
    return get_syntax_tree_from_sail(sail)


def get_syntax_tree_from_sail(sail):
    states = States()
    sail = sail.replace("\t", "")

    newline_count = 1
    objects = [SailObject(f"undefined_function", ObjectType.FUNCTION, newline_count, [])]
    root_object = objects[-1]
    objects_map = {"undefined_function": [root_object]}

    curr_string = ""
    j = 0
    while j < len(sail):
        prev_char = None if j <= 0 else sail[j - 1]
        curr_char = sail[j]
        next_char = None if j >= len(sail) - 1 else sail[j + 1]

        # print(curr_string)
        # print([(o.name, o.object_type.value) for o in objects])
        if is_newline(curr_char):
            newline_count += 1
            j += 1
            continue
        elif is_quote(curr_char, states):
            if states.is_quote:
                objects, object_map = process_new_object("\"" + curr_string.strip() + "\"", ObjectType.TEXT, objects, objects_map,
                                                         newline_count, states)
                objects = objects[:-2]  # Text objectTypes cannot own values
                curr_string = ""
            j += 1
            states.is_quote = not states.is_quote
            continue
        elif is_single_quote(sail, j, states):
            if states.is_single_quote:
                objects, object_map = process_new_object("\'" + curr_string.strip() + "\'", ObjectType.TEXT, objects, objects_map,
                                                         newline_count, states)
                objects = objects[:-2]  # Text objectTypes cannot own values
                curr_string = ""
            j += 1
            states.is_single_quote = not states.is_single_quote
            continue
        elif is_start_of_comment(curr_char, next_char, states):
            states.is_comment = True
            curr_string = ""
            j += 2
            continue
        elif is_end_of_comment(curr_char, next_char, states):
            states.is_comment = False
            j += 2
            objects, object_map = process_new_object("/*" + curr_string + "*/", ObjectType.COMMENT, objects, objects_map,
                                                     newline_count, states)
            objects = objects[:-2]  # Comment objectTypes cannot own values
            curr_string = ""
            continue
        elif is_start_of_type_constructor_name(sail, j, states):
            states.is_type_constructor = True
            j += len(TYPE_CONSTRUCTOR_STARTS_WITH)
            curr_string = TYPE_CONSTRUCTOR_STARTS_WITH
            continue
        elif is_end_of_type_constructor_name(curr_char, states):
            j += 1
            states.is_type_constructor = False
            objects, object_map = process_new_object(curr_string.strip() + "\'", ObjectType.FUNCTION, objects,
                                                     objects_map, newline_count, states)
            curr_string = ""
            continue
        elif is_start_of_type_constructor(curr_char, objects, states):
            j += 1
            continue
        elif is_start_bracket_index(curr_char, states):
            if curr_string.strip() == 0:
                objects.append(objects[-1].values[-1])
                objects.append(objects[-1].values[-1])
            else:
                objects, object_map = process_new_object(curr_string.strip(), get_value_type(curr_string.strip()),
                                                         objects, objects_map, newline_count, states)
            objects, object_map = process_new_object(f"undefined_index_{uuid.uuid4()}", ObjectType.INDEX,
                                                     objects, objects_map, newline_count, states)
            curr_string = ""
            j += 1
            continue
        elif is_end_bracket_index(curr_char, states):
            if len(curr_string.strip()) > 0:
                objects, object_map = process_new_object(curr_string.strip(), get_value_type(curr_string.strip()),
                                                         objects, objects_map, newline_count, states)
                objects = objects[:-2]
            objects = objects[:-2]  # [...,function,index] -> [...,function]
            curr_string = ""
            j += 1
            continue
        elif is_start_function(curr_char, states):
            if len(curr_string.strip()) == 0:
                curr_string = f"undefined_function_{uuid.uuid4()}"
            objects, object_map = process_new_object(curr_string.strip(), ObjectType.FUNCTION, objects,
                                                     objects_map, newline_count, states)
            curr_string = ""
            j += 1
            states.is_function_name = False
            continue
        elif is_end_function(curr_char, states):
            if len(curr_string.strip()) > 0:
                objects, object_map = process_new_object(curr_string.strip(), get_value_type(curr_string.strip()),
                                                         objects, objects_map, newline_count, states)
                if objects[-2].object_type in [ObjectType.PARAMETER, ObjectType.INDEX]:
                    objects = objects[:-2]  # Text objectTypes cannot own values
            if len(objects) == 1:
                objects = objects[:-1]
            elif objects[-1].object_type == ObjectType.FUNCTION and objects[-2].object_type == ObjectType.PARAMETER:
                objects = objects[:-2]  # [...,function,param,function] -> [...,function]
            curr_string = ""
            j += 1
            continue
        elif is_dot_notation(curr_char, states, curr_string):
            if objects[-1].object_type == ObjectType.PARAMETER:
                objects, object_map = process_new_object(curr_string.strip(), get_value_type(curr_string.strip()),
                                                         objects, objects_map, newline_count, states)
                objects = objects[:-2]
            if curr_string.strip() == 0:
                objects.append(objects[-1].values[-1])
                objects.append(objects[-1].values[-1])
            objects, object_map = process_new_object(f"undefined_index_{uuid.uuid4()}", ObjectType.INDEX,
                                                     objects, objects_map, newline_count, states)
            curr_string = ""
            j += 1
            continue
        elif is_start_variant(curr_char, states):
            objects, object_map = process_new_object(f"variant_{uuid.uuid4()}", ObjectType.FUNCTION, objects,
                                                     objects_map, newline_count, states)
            j += 1
            continue
        elif is_end_variant(curr_char, states):
            if len(curr_string.strip()) > 0:
                objects, object_map = process_new_object(curr_string.strip(), get_value_type(curr_string.strip()),
                                                         objects, objects_map, newline_count, states)
                objects = objects[:-2]  # Text objectTypes cannot own values
            objects = objects[:-2]  # [...,function,param,function] -> [...,function] or [function] -> []
            curr_string = ""
            j += 1
            continue
        elif if_next_list_value(curr_char, states):
            if len(curr_string.strip()) > 0:
                objects, object_map = process_new_object(curr_string.strip(), get_value_type(curr_string.strip()),
                                                         objects, objects_map, newline_count, states)
                objects = objects[:-2]  # [...,function,param,value] -> [...,function]
            if objects[-1].object_type in [ObjectType.RI, ObjectType.LOCAL, ObjectType.FV]:
                objects = objects[:-2]
            curr_string = ""
            j += 1
            continue
        elif is_start_keyed_parameter(curr_char, states):
            if objects[-1].object_type != ObjectType.FUNCTION:
                objects = objects[:-1]  # [...,function,param] -> [...,function]
            objects, object_map = process_new_object(curr_string.strip(), ObjectType.PARAMETER, objects,
                                                     objects_map, newline_count, states)
            curr_string = ""
            j += 1
            continue
        elif is_start_function_name(sail, j, states):
            states.is_function_name = True
            curr_string += sail[j:j+2]
            j += 2
            continue
        elif is_end_function_name(curr_char, states):
            states.is_function_name = False
            j += 1
            continue
        elif is_conditional_operator(sail, j, states):
            if sail[j:j + 8] in ["&lt;&gt;"]:
                curr_string += sail[j:j + 8]
                j += 8
                continue
            elif sail[j:j + 5] in ["&lt;=", "&gt;="]:
                curr_string += sail[j:j + 5]
                j += 5
                continue
            elif sail[j:j + 4] in ["&lt;", "&gt;"]:
                curr_string += sail[j:j + 4]
                j += 4
                continue
            elif sail[j] in ["="]:
                curr_string += sail[j:j + 1]
                j += 1
                continue
            objects.append(objects[-1].values[-1])
            objects.append(objects[-1].values[-1])

        curr_string += curr_char
        j += 1

    return root_object, objects_map


def get_sail_expression(xml_path: Path):
    with open(xml_path, "r") as infile:
        xml = infile.read()
    return re.search(r"<definition>([\S\s.]*?)</definition>", xml).group(1)


def get_value_type(string: str):
    if "ri!" in string:
        return ObjectType.RI
    elif "local!" in string:
        return ObjectType.LOCAL
    elif "fv!" in string:
        return ObjectType.FV
    return ObjectType.TEXT


def is_newline(c: str):
    return c in ["\n", "\r"]


def is_quote(c: str, states: States):
    return c == "\"" and not states.is_single_quote and not states.is_comment \
           and not states.is_type_constructor and not states.is_function_name


def is_single_quote(string: str, j: int, states: States):
    return string[j:j + len(TYPE_CONSTRUCTOR_STARTS_WITH)] != TYPE_CONSTRUCTOR_STARTS_WITH and string[j] == "\'" \
           and not states.is_quote and not states.is_comment \
           and not states.is_type_constructor and not states.is_function_name


def is_start_of_comment(c: str, n: str, states: States):
    return c == "/" and n == "*" and not states.is_quote and not states.is_function_name \
           and not states.is_single_quote and not states.is_type_constructor


def is_end_of_comment(c: str, n: str, states: States):
    return c == "*" and n == "/" and not states.is_quote and not states.is_function_name \
           and not states.is_single_quote and not states.is_type_constructor


def is_start_of_type_constructor_name(string: str, j: int, states: States):
    return string[j:j + len(TYPE_CONSTRUCTOR_STARTS_WITH)] == TYPE_CONSTRUCTOR_STARTS_WITH \
           and not states.is_single_quote and not states.is_comment and not states.is_quote \
            and not states.is_function_name


def is_end_of_type_constructor_name(c: str, states: States):
    return states.is_type_constructor and c == "\'" and not states.is_quote and not states.is_comment \
           and not states.is_single_quote and not states.is_function_name


def is_start_of_type_constructor(c: str, objects: List[SailObject], states: States):
    return c in ["("] and TYPE_CONSTRUCTOR_STARTS_WITH in objects[-1].name and not states.is_quote \
           and not states.is_single_quote and not states.is_comment and not states.is_function_name


def is_start_bracket_index(c: str, states: States):
    return c == "[" and not states.is_quote and not states.is_comment and not states.is_type_constructor \
           and not states.is_single_quote and not states.is_function_name


def is_end_bracket_index(c: str, states: States):
    return c == "]" and not states.is_quote and not states.is_comment and not states.is_type_constructor \
           and not states.is_single_quote and not states.is_function_name


def is_conditional_operator(string: str, j: int, states: States):
    return (string[j:j+8] in ["&lt;&gt;"] or string[j:j+5] in ["&lt;=", "&gt;="] or string[j:j+4] in ["&lt;", "&gt;"] \
            or string[j:j+2] in ["&lt;&gt;", "&lt;=", "&gt;="] or string[j] in ["&lt;", "&gt;", "="]) \
            and not states.is_quote and not states.is_single_quote and not states.is_comment \
            and not states.is_type_constructor and not states.is_function_name


def is_start_function(c: str, states: States):
    return c in ["("] and not states.is_quote and not states.is_single_quote and not states.is_comment \
           and not states.is_type_constructor


def is_end_function(c: str, states: States):
    return c in [")"] and not states.is_quote and not states.is_single_quote and not states.is_comment \
           and not states.is_type_constructor


def is_dot_notation(c: str, states: States, string):
    return c == "." and not states.is_quote and not states.is_single_quote and not states.is_comment \
           and not states.is_type_constructor and not states.is_function_name


def is_start_variant(c: str, states: States):
    return c == "{" and not states.is_quote and not states.is_single_quote and not states.is_comment \
           and not states.is_type_constructor


def is_end_variant(c: str, states: States):
    return c == "}" and not states.is_quote and not states.is_single_quote and not states.is_comment \
           and not states.is_type_constructor


def if_next_list_value(c: str, states: States):
    return c == "," and not states.is_quote and not states.is_single_quote \
           and not states.is_comment and not states.is_type_constructor


def is_start_keyed_parameter(c: str, states: States):
    return c == ":" and not states.is_quote and not states.is_single_quote \
           and not states.is_comment and not states.is_type_constructor


def is_start_function_name(string: str, j: int, states: States):
    return string[j:j+2] == "#\"" and not states.is_quote and not states.is_single_quote \
           and not states.is_comment and not states.is_type_constructor


def is_end_function_name(c: str, states: States):
    return c == "\"" and states.is_function_name


def process_new_object(
        object_name: str,
        object_type: ObjectType,
        objects: List[SailObject],
        objects_map: Dict[str, List[SailObject]],
        newline_count: int,
        states: States
) -> Tuple[List[SailObject], Dict[str, List[SailObject]]]:
    print(object_name, object_type)
    sail_object = SailObject(object_name, object_type, newline_count, [])
    if len(objects) == 1 and objects[-1].name == "undefined_function" and object_type == ObjectType.FUNCTION:
        objects[-1].name = object_name
        objects_map[object_name] = [] if object_name not in objects_map else objects_map[object_name]
        objects_map[object_name].append(objects[-1])
        objects_map["undefined_function"] = objects_map["undefined_function"][:-1]
    elif objects[-1].object_type == ObjectType.FUNCTION and object_type not in [ObjectType.PARAMETER, ObjectType.INDEX]:
        param_sail_object = SailObject(f"undefined_parameter_{uuid.uuid4()}", ObjectType.PARAMETER,
                                       newline_count, [sail_object])
        objects[-1].add_value(param_sail_object)
        objects.append(param_sail_object)
        objects.append(sail_object)
        objects_map["undefined_parameter"] = [] if object_name not in objects_map else objects_map[object_name]
        objects_map["undefined_parameter"].append(param_sail_object)
        objects_map[object_name] = [] if object_name not in objects_map else objects_map[object_name]
        objects_map[object_name].append(sail_object)
    else:
        objects[-1].add_value(sail_object)
        objects.append(sail_object)
        objects_map[object_name] = [] if object_name not in objects_map else objects_map[object_name]
        objects_map[object_name].append(sail_object)
    print("\t", states.is_function_name, [(o.name, o.object_type.value) for o in objects])
    return objects, objects_map


if __name__ == "__main__":
    file_path = Path(__file__)
    resources_path = file_path.parent.parent / "resources"
    getJsonFromFilters_path = resources_path / "PHQ_getJsonFromFilters.xml"
    toplevel_path = resources_path / "PHQ_topLevel.xml"
    profileDetailsVendorDetails_path = resources_path / "AS_VM_FM_profileDetailsVendorDetails.xml"
    profileDetailsPrimary_path = resources_path / "AS_VM_FM_profileDetailsPrimary.txt"

    top_object, names_map = get_syntax_tree_from_xml(resources_path / "PHQ_getAttributeData.xml")

    stack = [(0, top_object)]
    while stack:
        l, o = stack[-1]
        stack = stack[:-1]
        for v in o.values[::-1]:
            stack.append((l + 1, v))
        print(f"{'  ' * l}{o.get_print()}")

    for name in ["label", "a!localVariables", "filterMeasure", "stampIcon"]:
        if name in names_map:
            print(f"Name: {name}")
            for o in names_map[name]:
                print(f"\tName: {[(v.name, v.object_type.value, v.line) for v in o.values]}")
