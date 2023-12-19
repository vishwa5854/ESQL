import subprocess
import sys


# Get input parameters, return a dictionary
def parse_input(file_name):
    with open(file_name, 'r') as file:
        lines = file.readlines()

    input_params = {"s": [], "n": 0, "v": [], "f": [], "p": [], "g": ""}

    sections = ["s", "n", "v", "f", "p", "g"]
    section = None

    for line in lines:
        line = line.strip()
        if line[:-1] in sections:
            section = line[:-1]
            continue
        if section == "s":
            input_params[section] = [item.strip() for item in line.split(",")]
        elif section == "n":
            input_params[section] = int(line)
        elif section == "v":
            input_params[section] = [item.strip() for item in line.split(",")]
        elif section == "f":
            input_params[section] = [item.strip() for item in line.split(",")]
        elif section == "p":
            input_params[section].append(line)
        elif section == "g":
            input_params[section] = line

    return input_params


def phi(s: [str], n: int, v: [str], f: [str], p: [str], g: str):
    """
    This function is responsible for creating MF_STRUCT for the given 6 parameters of PHI operator
    :param s - List of projected attributes for the query output
    :param n - Number of grouping variables
    :param v - List of grouping attributes
    :param f - list of sets of aggregate functions. Fi represents a list of aggregate functions for each grouping var
                Eg: [count_1_quant, sum_2_quant, avg_2_quant, max_3_quant]
    :param p - list of predicates to define the ranges for the grouping variables
    :param g - Predicate for having clause
    """
    class_variables = ""
    class_variable_names = "["

    # Init of f members to corresponding values like for max default should be -1, for min default should be MAX_NUM
    # for sum, it would be 0, count = 0, avg = 0
    for j in v:
        class_variables += f"""        {j} = ""\n"""
        class_variable_names += f"'{j}', "
    for j in f:
        aggregate_function = j.split('_')[0]
        class_variable_names += f"'{j}', "

        if aggregate_function == "sum":
            class_variables += f"""        {j} = 0\n"""
        elif aggregate_function == "count":
            class_variables += f"""        {j} = 0\n"""
        elif aggregate_function == "avg":
            class_variables += f"""        {j} = 0\n"""
        elif aggregate_function == "max":
            class_variables += f"""        {j} = -1\n"""
        elif aggregate_function == "min":
            class_variables += f"""        {j} = float('inf')\n"""
        else:
            class_variables += f"""        {j} = ""\n"""
    class_variables = class_variables[4:]
    class_variable_names = class_variable_names[:-2] + "]"
    key = "("

    for i in v:
        key += f"row.get('{i}'), "
    key = key[:-2] + ")"
    group_by_values_insertion = ""

    for i in v:
        group_by_values_insertion += f"        data[pos].{i} = row.get('{i}')\n"

    aggregate_loops = ""

    local_variables_for_aggregate = ""

    # We need to insert local variables so that the predicates can use them
    for i in class_variable_names[1: -1].replace("'", '').split(", "):
        local_variables_for_aggregate += f"        {i} = data[pos].{i}\n"

    # we are generating for loops for each aggregate function with their respective predicates
    # 1.state='NY'
    for i in f:
        aggregate_function, gv_num, aggregate_attribute = i.split("_")
        predicate = p[int(gv_num)]
        predicate = predicate.replace(f"{gv_num}.", "row.get('")
        predicate = predicate.replace("==", "')==")
        predicate = predicate.replace(">", "')>")
        predicate = predicate.replace("<", "')<")
        aggregate_string = ""

        if aggregate_function == "sum":
            aggregate_string = f"data[pos].{i} + row.get('{aggregate_attribute}')"
        elif aggregate_function == "count":
            aggregate_string = f"data[pos].{i} + 1"
        elif aggregate_function == "min":
            aggregate_string = f"min(data[pos].{i}, row.get('{aggregate_attribute}'))"
        elif aggregate_function == "max":
            aggregate_string = f"max(data[pos].{i}, row.get('{aggregate_attribute}'))"
        elif aggregate_function == "avg":
            pass
            # TODO: Figure out the denominator somehow

        aggregate_loops += (f"    cur.scroll(0, mode='absolute')\n\n    for row in cur:\n        key = {key}\n"
                            f"        pos = group_by_map[key]\n{local_variables_for_aggregate}\n        "
                            f"if {predicate}:\n")
        aggregate_loops += f"            data[pos].{i} = {aggregate_string}\n"

    # Prepare the HAVING clause logic
    having_clause = ""
    if g:
        # Replace aggregate function names in the HAVING clause with corresponding attributes
        for agg_func in f:
            g = g.replace(agg_func, f"obj.{agg_func}")
        having_clause = f"    data = [obj for obj in data if {g}]\n"

    return f"""
    class MFStruct:
    {class_variables}
    data = []
    
    # For all the grouping variables
    group_by_map = dict()
    
    for row in cur:
        key = {key}
        
        if (not group_by_map.get(key)) and (group_by_map.get(key) != 0):
            data.append(MFStruct())
            group_by_map[key] = len(data) - 1
        
        pos = group_by_map.get(key)
{group_by_values_insertion}
    # We need to compute values to the aggregate functions with their corresponding grouping variable predicate.
{aggregate_loops}
    # Apply HAVING clause if present
{having_clause}
    table = PrettyTable()
    table.field_names = {class_variable_names}
    
    for obj in data:
        temp = []
        
        for j in table.field_names:
            temp.append(getattr(obj, j))
        table.add_row(temp)

    # Printing the table
    return table
"""


def main(input_file):
    """
    This is the generator code. It should take in the MF structure and generate the code
    needed to run the query. That generated code should be saved to a 
    file (e.g. _generated.py) and then run.
    """

    input_params = parse_input(f"input/{input_file}")

    # We are going to add a predicate for the default grouping variable 0 based on the group by attributes
    predicates = input_params["p"]
    group_by_attributes = input_params["v"]
    new_predicates = ""

    for i in group_by_attributes:
        new_predicates += f"0.{i}=={i} and "
    new_predicates = new_predicates[:-5]
    predicates.insert(0, new_predicates)

    body = phi(input_params['s'], input_params['n'], input_params["v"], input_params["f"], predicates,
               input_params["g"])
    # body = phi(['s'], 3, ['cust', 'prod'], ['count_1_quant', 'sum_2_quant', 'min_2_quant', 'max_3_quant'],
    #            ["1.state=='NY' and 1.quant>10 and 1.cust=='Sam'", "2.state=='NJ'", "3.state=='CT'"], "")

    # Note: The f allows formatting with variables.
    #       Also, note the indentation is preserved.
    tmp = f"""
import os
import psycopg2
import psycopg2.extras
from prettytable import PrettyTable
from dotenv import load_dotenv

# DO NOT EDIT THIS FILE, IT IS GENERATED BY generator.py


def query():
    load_dotenv()

    user = os.getenv('USERNAMEZ')
    password = os.getenv('PASSWORD')
    dbname = os.getenv('DBNAME')

    conn = psycopg2.connect("dbname="+dbname+" user="+user+" password="+password,
                            cursor_factory=psycopg2.extras.DictCursor, host='127.0.0.1', port='5432')
    cur = conn.cursor()
    cur.execute("SELECT * FROM sales")
    
    _global = []
    {body}
    
def main():
    print(query())
    
    
if "__main__" == __name__:
    main()
    """

    # Write the generated code to a file
    open("_generated.py", "w").write(tmp)
    # Execute the generated code
    subprocess.run(["python", "_generated.py"])


if "__main__" == __name__:
    main(sys.argv[1])
    # print(phi(['s'], 3, ['cust'], ['count_1_quant', 'sum_2_quant', 'avg_2_quant', 'max_3_quant'], [None], ""))
