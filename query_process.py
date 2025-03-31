import re
from itertools import combinations, product

def table_check(table, cond):
    '''Check if the cond is on the given table
    '''
    escaped_table = re.escape(table)
    pattern = r'\b{}\.\w+'.format(escaped_table)
    match = re.search(pattern, cond, re.IGNORECASE)
    return match is not None  

def parse_query(query):
    '''Given a query, find out all tables and store their own predicates, also find all pairs of joins and the join condition
    '''
    ### Extract FROM clause
    from_clause = re.search(r'FROM(.*)\s*WHERE', query, re.DOTALL)
    from_clause = from_clause.group(1).strip()
    alias_pattern = re.compile(r'(\w+)\s+AS\s+(\w+)', re.IGNORECASE)
    table_pairs = alias_pattern.findall(from_clause)
    table_dict = {pair[1]:{
        "full_name":pair[0],
        "predicates":[]
        } for pair in table_pairs}
    join_dict = {}

    ### Extract WHERE clause
    where_clause = re.search(r'WHERE(.*);', query, re.DOTALL)
    where_clause = where_clause.group(1).strip()
    where_clause = re.sub(r'\s+', ' ', where_clause)    # trim new line char and extra spaces
    conds = re.split(r'\bAND\b', where_clause)          # identify all conditions, separated by AND
    conds = [cond.strip() for cond in conds]            # remove empty strings and strip spaces

    ### Separate JOIN conds and predicates
    join_pattern = re.compile(r'\b(\w+)\.\w+\s*=\s*(\w+)\.\w+\b')

    for cond in conds:
        if join_pattern.search(cond):
            pairs = re.findall(join_pattern, cond)[0]
            join_dict['-'.join(pairs)] = cond
            join_dict['-'.join((pairs[1], pairs[0]))] = cond
        else:
            pattern = r'(\w+)\.'
            ### Search for the pattern in the condition
            table = re.search(pattern, cond).group(1)
            table_dict[table]["predicates"].append(cond)

    return table_dict, join_dict

def get_all_join(dims, query):
    '''Get all joins. If dim1 and dim2 are joint, but dim2 and dim3 also can be joint and generates error, 
    need to join dim3 as well
    '''
    table_dict, join_dict = parse_query(query)
    full_join = []
    simple_join = True
    if table_dict[dims[0]]["predicates"] != [] or table_dict[dims[1]]["predicates"] != [] :
        return [d for d in dims], simple_join
    else:
        for dim in dims:
            joins = []
            for t in table_dict.keys():
                if t+"-"+dim in join_dict and table_dict[t]["predicates"] != []:
                    joins.append([dim, t])
                    simple_join = False
            if joins == []:
                joins = dim
            full_join.append(joins)
        return full_join, simple_join

def gen_sub_query(dims, query, full=False):
    sub_query = "SELECT * FROM "
    table_dict, join_dict = parse_query(query)
    for d in dims:
        full_name = table_dict[d]["full_name"]
        sub_query += f"{full_name} AS {d}, "
    sub_query = sub_query[:-2]  # trim the last , 
    trim = False
    if not full:
        sub_query += " WHERE "
        for d in dims:
            if table_dict[d]["predicates"] != []:
                for predicate in table_dict[d]["predicates"]:
                    sub_query += f"{predicate} AND "
                    trim = True
    if len(dims) > 1:
        for d1, d2 in combinations(dims, 2):
            if d1+"-"+d2 in join_dict:
                sub_query += join_dict[d1+"-"+d2] + " AND "
                trim = True
    if trim:
        sub_query = sub_query[:-5]  # trim the last AND
    elif not full:
        sub_query = sub_query[:-7]  # trim the WHERE if no predicates are added
    return sub_query + ";"

if __name__ == "__main__":
    query = '''
    SELECT MIN(mc.note) AS production_note,
        MIN(t.title) AS movie_title,
        MIN(t.production_year) AS movie_year
    FROM company_type AS ct,
        info_type AS it,
        movie_companies AS mc,
        movie_info_idx AS mi_idx,
        title AS t
    WHERE ct.kind = 'production companies'
    AND it.info = 'top 250 rank'
    AND mc.note NOT LIKE '%(as Metro-Goldwyn-Mayer Pictures)%'
    AND (mc.note LIKE '%(co-production)%'
        OR mc.note LIKE '%(presents)%')
    AND ct.id = mc.company_type_id
    AND t.id = mc.movie_id
    AND t.id = mi_idx.movie_id
    AND mc.movie_id = mi_idx.movie_id
    AND it.id = mi_idx.info_type_id;
    '''
    # print(gen_sub_query("mc", query))
    # print(gen_sub_query("mc", query, full=True))
    # print(gen_sub_query("t", query))
    # print()
    # print(gen_sub_query("mc-t", query))
    # print(get_all_join(["mc","t"], query))
    # table, join = parse_query(query)
    # print(table)
    # print()
    # print(join)
    print(list(product(*['a', [['b','c'],['b','d']]])))
    print(list(product(*[[['a','c'],['a','d']], [['b','c'],['b','d']]])))
