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

    for i in [v, f]:
        for j in i:
            class_variables += f"""        {j} = ""\n"""
    class_variables = class_variables[4:]
    key = "("

    for i in v:
        key += f"row['{i}'],"
    key = key[:-1] + ")"
    group_by_values_insertion = ""

    for i in v:
        group_by_values_insertion += f"        data[pos].{i} = row['{i}']\n"

    return f"""
    class MFStruct:
    {class_variables}
    data = []
    
    # For all the grouping variables bruh
    group_by_map = dict()
    
    for row in cur:
        key = {key}
        
        if (not group_by_map.get(key)) and (group_by_map.get(key) != 0):
            data.append(MFStruct())
            group_by_map[key] = len(data) - 1
        
        pos = group_by_map.get(key)
{group_by_values_insertion}"""


def main(input_file):
    """
    This is the generator code. It should take in the MF structure and generate the code
    needed to run the query. That generated code should be saved to a 
    file (e.g. _generated.py) and then run.
    """

    input_params = parse_input(f"input/{input_file}")
    body = phi(input_params['s'], input_params['n'], input_params["v"], input_params["f"], input_params["p"], input_params["g"])
    # body = phi(['s'], 3, ['cust', 'prod'], ['count_1_quant', 'sum_2_quant', 'avg_2_quant', 'max_3_quant'], [None], "")

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
    table = PrettyTable()
    table.field_names = data[0].__dict__.keys()
    
    for obj in data:
        temp = []
        
        for j in obj.__dict__.keys():
            temp.append(obj.__dict__[j])
        table.add_row(temp)

    # Printing the table
    return table


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
