from flask import Blueprint, render_template, request, jsonify
import os
import re
import pandas as pd
import json
from demo_model import Demo
import prep_query_template as pqt

from sqlalchemy import create_engine

bp = Blueprint('index', __name__)

# SQLVIS modified code
# conn = psycopg2.connect(
#     dbname="imdbloadbase",
#     user="lsh",
#     password="your_password",
#     host="/tmp"
# )

# With sqlalchemy, the warning of pandas can be cleared
conn = create_engine('postgresql+psycopg2://lsh:your_password@/imdbloadbase?host=/tmp')


def personalized_schema_from_conn(conn):
    schema = {}
    tableQuery = """
    SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';
    """
    tables = pd.read_sql_query(tableQuery, conn)['tablename']

    for table_name in tables:
        headerQuery = f"SELECT * FROM {table_name} WHERE 1=0;"
        headers = list(pd.read_sql_query(headerQuery, conn).columns)
        schema[table_name] = headers

    return schema


def personalized_visualize(s, schema, dir_path, query_index, basicStats, sensitiveData):
    query = s.replace("'", "\\'")
    query = query.replace('\n', ' ')
    query = query.replace('\r', ' ')
    query = re.sub(r'\s+', ' ', query)
    
    shortSchema = json.dumps(schema)

    html_content = f"""
    <link rel="stylesheet" type="text/css" href="{dir_path}/styles.css.html">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/require.js/2.3.6/require.min.js"></script>
    <script>
        require.config({{
            paths: {{
                'd3': 'https://d3js.org/d3.v4.min',
                'Plotly': 'https://cdn.plot.ly/plotly-latest.min'
            }},
            shim: {{
                'viz': {{
                    deps: ['d3', 'Plotly']
                }}
            }}
        }});
        
        require(['viz'], function(viz) {{
            var query = '{query}';
            var schema = {shortSchema};
            var query_index = '{query_index}';
            var basicStats = {basicStats};
            var sensitiveData = {sensitiveData};
            viz(document.body, query, schema, query_index, basicStats, sensitiveData);
        }});
    </script>
    <script src="{dir_path}/visualize.js"></script>
    """

    
    return html_content


# Example query templates
query_to_local_selection_dict = {
        '33a': ['cn', 'it_miidx', 'it_miidx', 'kt', 'kt', 'lt', 'mi_idx', 't'],
        '32a': ['k'],
        '31a': ['ci', 'cn', 'it_mi', 'it_miidx', 'k', 'mi', 'n'],
        '30a': ['cct', 'cct', 'ci', 'it_mi', 'it_miidx', 'k', 'mi', 'n', 't'],
        '29a': ['cct', 'cct', 'chn', 'ci', 'cn', 'it_mi', 'it_pi', 'k', 'mi', 'n', 'rt', 't'],
        '28a': ['cct', 'cct', 'cn', 'it_mi', 'it_miidx', 'k', 'kt', 'mc', 'mi', 'mi_idx', 't'],
        '27a': ['cct', 'cct', 'cn', 'ct', 'k', 'lt', 'mc', 'mi', 't'],
        '26a': ['cct', 'cct', 'chn', 'it_miidx', 'k', 'kt', 'mi_idx', 't'],
        '25a': ['ci', 'it_mi', 'it_miidx', 'k', 'mi', 'n'],
        '24a': ['ci', 'cn', 'it_mi', 'k', 'mi', 'n', 'rt', 't'],
        '23a': ['cct', 'cn', 'it_mi', 'kt', 'mi', 't'],
        '22a': ['cn', 'it_mi', 'it_miidx', 'k', 'kt', 'mc', 'mi', 'mi_idx', 't'],
        '21a': ['cn', 'ct', 'k', 'lt', 'mc', 'mi', 't'],
        '20a': ['cct', 'cct', 'chn', 'k', 'kt', 't'],
        '19a': ['ci', 'cn', 'it_mi', 'mc', 'mi', 'n', 'rt', 't'],
        '18a': ['ci', 'it_mi', 'it_miidx', 'n'],
        '17a': ['cn', 'k', 'n'], 
        '16a': ['cn', 'k', 't'],
        '15a': ['cn', 'it_mi', 'mc', 'mi', 't'],
        '14a': ['it_mi', 'it_miidx', 'k', 'kt', 'mi', 'mi_idx', 't'],
        '13a': ['cn', 'ct', 'it_miidx', 'it_mi', 'kt'],
        '12a': ['cn', 'ct', 'it_mi', 'it_miidx', 'mi', 'mi_idx', 't'],
        '11a': ['cn', 'ct', 'k', 'lt', 'mc', 't'],
        '10a': ['ci', 'cn', 'rt', 't'],
        '9a': ['ci', 'cn', 'mc', 'n', 'rt', 't'],
        '8a': ['ci', 'cn', 'mc', 'n', 'rt'],
        '7a': ['an', 'it_pi', 'lt', 'n', 'pi', 't'],
        '6a': ['k', 'n', 't'],
        '5a': ['ct', 'mc', 'mi', 't'],
        '4a': ['it_miidx', 'k', 'mi_idx', 't'],
        '3a': ['k', 'mi', 't'],
        '2a': ['cn', 'k'],
        '1a': ['ct', 'it_miidx', 'mc']}

def sort_helpers(text):
    return [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', text)]

def example_queries():
    query_dir = 'app/static/query/join-order-benchmark'
    queries = []
    for file_name in os.listdir(query_dir):
        if file_name.endswith('.sql'):
            path = os.path.join(query_dir, file_name)
            with open(path, 'r') as file:
                content = file.read()
            queries.append({'name': file_name, 'content': content})
    queries.sort(key=lambda x: sort_helpers(x['name']))
    return queries  

def sample_queries():
    queries_dict = {}
    query_ids = [f"{i}a" for i in range(1, 34)]  # 1a - 33a
    for query_id in query_ids:
        queries_dict[query_id], _ = pqt.gen_sql_by_template(query_id, K=20, db_name=None)
        
    return queries_dict

def template_queries():
    query_file = 'app/static/query/template.json'
    with open(query_file, 'r') as file:
        templates = json.load(file)['queries']
    
    queries = []
    for template in templates:
        query_id = template['query_id']
        query_info = {
            'name': query_id,
            'content': json.dumps(template['sql_template']),
            'placeholders': json.dumps(template['placeholders']),
            'hints': json.dumps(query_to_local_selection_dict.get(query_id, []))
        }
        queries.append(query_info)
    queries.sort(key=lambda x: sort_helpers(x['name']))
    # print(queries)
    return queries


# Get sensitive data
def load_json_data(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def get_matching_stats(basic_stats, sensitive_data):
    matching_stats = {}
    for key in basic_stats.keys():
        is_sensitive = key in sensitive_data
        matching_stats[key] = basic_stats[key]
        matching_stats[key]['isSensitive'] = is_sensitive
    return matching_stats



###########################################
schema = personalized_schema_from_conn(conn)
demo_model = None
global_matching_stats = {} # global variable for matching_stats - update when having new visualization
samples = sample_queries() # global variable

@bp.route('/', methods=['GET', 'POST'])
def index():
    visualization = None
    examples = example_queries()
    templates = template_queries()
    last_query = ""
    last_file = ""
    basic_stats = {}
    sensitive_data = {}
    matching_stats = {}
    latency_info_dict = {}
    cost_info_dict = {}
    if request.method == 'POST':
        try:
            sql_query = request.form.get('sql_query', '')
            last_query = sql_query
            last_file = request.form.get('query_file', '')
            dir_path = '/static'
            query_index, _ = last_file.split('.')
            
            # sensitive data for interactive purpose
            global demo_model
            demo_model = Demo(query_id=query_index, input_sql=last_query)
            basic_stats_dict, basic_stats = demo_model.get_basic_info()
            sensitive_data_dict, sensitive_data = demo_model.get_sensitive_dim()
            # latency_info_dict, latency_info = demo_model.get_latency_info()
            cost_info_dict, cost_info = demo_model.get_cost_info()

            # sort the matching_stats
            matching_stats = get_matching_stats(basic_stats_dict, sensitive_data_dict)
            matching_stats = {k: v for k, v in sorted(matching_stats.items(), key=lambda item: (not item[1]['isSensitive'], item[1]['selectivity']), reverse=False)}
            global global_matching_stats
            global_matching_stats = matching_stats # MARK: update global_matching_stats
            
            visualization = personalized_visualize(sql_query, schema, dir_path, query_index, basic_stats, sensitive_data)
                    
        except Exception as e:
            print(f"Error during visualization: {str(e)}")
    
                
    return render_template('index.html', last_query=last_query, last_file=last_file, visualization=visualization, examples=examples, samples=samples, templates=templates, matching_stats=matching_stats, cost_info_dict=cost_info_dict)


###########################################
# Workload Sample
@bp.route('/next_query', methods=['POST'])
def next_query():
    query_id = request.form['queryId']
    index = int(request.form['index'])
    sql_list = samples.get(query_id, [])

    next_index = (index + 1) % len(sql_list)
    return jsonify({
        'sql': sql_list[next_index],
        'queryFile': f"{query_id}.sql",
        'index': next_index
    })


###########################################
# Cost & Latency
@bp.route('/get_cost', methods=['POST'])
def get_cost():
    try:
        updated_data = {key: request.form[key] for key in request.form}
        demo_model.inject_input_sel(updated_data)
        print("Updated Selectivity Data:", updated_data)
        
        # return updated latency & cost
        cost_info_dict, cost_info = demo_model.get_cost_info()
        return jsonify(cost_info_dict=cost_info_dict)
        
    except Exception as e:
        print("Error retrieving cost info:", e)
        return jsonify(error=str(e)), 400
    
    
@bp.route('/get_latency', methods=['GET'])
def get_latency():
    try:
        if demo_model:
            latency_info_dict, latency_info = demo_model.get_latency_info()
            return jsonify(latency_info_dict=latency_info_dict)
        else:
            return jsonify(latency_info_dict={})
    except Exception as e:
        print("Error retrieving latency info:", e)
        return jsonify(error=str(e)), 400


###########################################
# Selectivity  
@bp.route('/update_selectivity_single', methods=['POST'])
def update_selectivity_single():
    key = request.form.get('key')
    new_value = demo_model.get_act_sel(key)

    return jsonify(newValue=new_value)


@bp.route('/reset_selectivity_single', methods=['POST'])
def reset_selectivity_single():
    key = request.form.get('key')
    try:
        if key in global_matching_stats:
            original_value = global_matching_stats[key]['selectivity']
            return jsonify(newValue=original_value)
        else:
            return jsonify(error="Key not found"), 404
    except Exception as e:
        print(f"Error resetting selectivity for {key}: {str(e)}")
        return jsonify(error=str(e)), 400
    

@bp.route('/change_all_selectivity', methods=['POST'])
def change_all_selectivity():
    print("current global_matching_stats keys:", global_matching_stats.keys())
    true_selectivity_stats = {}
    try:
        for key in global_matching_stats:
            new_value = demo_model.get_act_sel(key)
            true_selectivity_stats[key] = {'selectivity': new_value}

        return jsonify(true_selectivity_stats)
    except Exception as e:
        print(f"Error updating all selectivities: {str(e)}")
        return jsonify(error=str(e)), 400



@bp.route('/reset_all_selectivity', methods=['POST'])
def reset_all_selectivity():
    try:
        return jsonify(global_matching_stats)
    except Exception as e:
        print(f"Error resetting all selectivities: {str(e)}")
        return jsonify(error=str(e)), 400



###########################################
# Plan.html
@bp.route('/visualize_plan')
def show_plan():
    _, dynamicPlan = demo_model.rqo()
    _, cost = demo_model.get_all_cost_2d()
    return render_template('plan.html', dynamicPlan=dynamicPlan, dynamicCost=cost)
