import psycopg2
import time
import json
from tqdm import tqdm
from itertools import combinations, product


from sensitive_dict import *
from prep_error_list import *
from cached_robust_plan_dict import *

from prep_cardinality import get_maps, ori_cardest, write_to_file, write_pointers_to_file, get_raw_table_size
from postgres import get_all_plan_cost, get_real_latency, get_plan_cost
from prep_selectivity import prep_sel
from parse import gen_final_hint
from query_process import gen_sub_query, get_all_join
from gen_real_error import cal_local_selectivity, cal_join_selectivity

TIMES = 3   # to get latency, how many runs are needed
EXPLAIN = "EXPLAIN (SUMMARY, COSTS, FORMAT JSON)"
EXPLAIN_ALL = "EXPLAIN (ANALYZE, SUMMARY, COSTS, FORMAT JSON)"
file_of_base_sel = './cardinality/new_single.txt'  # file to be sent to pg folder, contains cardinality for base_rel
file_of_join_sel = './cardinality/join.txt'  # file to be sent to pg folder, contains cardinality for join_rel


class Demo():
    def __init__(self, db_name="imdbloadbase", query_id="2a",
                 method="sobol", rel_error=True, div=2, t=0.2, b=1, inst_id=-2, naive=False,
                 input_sql=""):
        ### Store the inputs
        self.db_name = db_name
        self.query_id = query_id
        self.method = method
        self.rel_error = rel_error
        self.div = div
        self.t = t
        self.b = b
        self.inst_id = inst_id
        self.naive = naive

        ##### Process db and query, load the cached sensitivity and errors
        if self.method == 'morris':
            cal_sen_method = '_morris'
            if self.db_name == 'imdbloadbase':
                sen_dict = sen_dict_morris  
            if db_name == 'dsb':
                sen_dict =  dsb_sen_dict_morris
            if db_name == 'stats':
                sen_dict =  stats_sen_dict_morris
        elif self.method == 'local':
            cal_sen_method = '_local'
            sen_dict = sen_dict_local
        else:
            cal_sen_method = ''
            if self.db_name == 'imdbloadbase':
                sen_dict = sen_dict_sobol  
            if self.db_name == 'dsb':
                sen_dict =  dsb_sen_dict_sobol
            if self.db_name == 'stats':
                sen_dict =  stats_sen_dict_sobol
        self.cal_sen_method = cal_sen_method
        self.sen_dict = sen_dict

        if self.db_name == 'stats':
            with open(f'./query/stats/stats_{self.query_id}.sql') as p:
                sql = p.read()
            err_files_dict = err_files_dict_stats
            rob_plan_dict = cached_rob_plan_dict_stats
        if self.db_name == 'imdbloadbase':
            with open('./query/join-order-benchmark/' + self.query_id + '.sql') as p:
                sql = p.read()
            err_files_dict = err_files_dict_job
            rob_plan_dict = cached_rob_plan_dict
        if self.db_name == 'dsb':
            with open(f'./query/dsb/query{self.query_id}_spj_1.sql') as p:
                sql = p.read()
            err_files_dict = err_files_dict_dsb
            rob_plan_dict = cached_rob_plan_dict_dsb
        self.err_files_dict = err_files_dict
        self.rob_plan_dict = rob_plan_dict

        if self.inst_id == 0:
            self.on_sample = "on-random/"   
            sql = modify_query("random_", "_4", sql)
        elif self.inst_id == -1:
            self.on_sample = "on-sample/"   
            sql = modify_query("sampled_", "_4", sql)
        elif self.inst_id >= 1:
            self.on_sample = "on-cat/"   
            sql = modify_query("cat_", f"_{self.inst_id}", sql)
        else:
            self.on_sample = 'on-base/' + db_name + '/'
            self.inst_id = None
        if input_sql != "":
            print(f"Input sql query from frontend: {input_sql}")
            sql = input_sql
        self.sql = sql

        ### Prepare the basic info
        ## Dimension info
        table_name_id_dict, join_map, join_info, pair_rel_info = get_maps(self.db_name, self.sql)
        self.join_map = join_map    # for prep_sel
        self.join_info = join_info  # for prep_sel
        self.num_of_base = len(table_name_id_dict)
        self.num_of_pair = len(pair_rel_info)
        self.num_of_join = len(join_info)
        self.num_of_all_basic = list(range(self.num_of_base + self.num_of_pair)) # basic includes single and pair
        dim_name2id_dict, dim_id2name_dict = {}, {}
        for id in range(self.num_of_base+self.num_of_pair):
            if id < self.num_of_base:
                name = list(table_name_id_dict.keys())[id]
            else:
                pair = pair_rel_info[id-self.num_of_base]
                name = pair[0] + '-' + pair[1]
            dim_name2id_dict[name] = id
            dim_id2name_dict[id] = name
        self.dim_name2id_dict = dim_name2id_dict
        self.dim_id2name_dict = dim_id2name_dict
        self.sen_dims = self.sen_dict[get_pure_q_id(self.query_id, self.db_name)]

        ## Estimated cardinality
        est_base_card, est_join_card_info = ori_cardest(self.db_name, self.sql)
        est_join_card = list(est_join_card_info[:, 2]) # all 2-way join estimated cardinality
        self.est_card = est_base_card + est_join_card

        ## Raw cardinality
        raw_base_card = get_raw_table_size(self.sql, self.db_name)
        raw_join_card = [i[2] for i in join_info]  # number of rows of left_table * number of rows of right_table
        self.raw_card = raw_base_card + raw_join_card

        ## Estimated selectivity: selectivity = est_card / raw_card
        est_base_sel = [est_base_card[i]/raw_base_card[i] for i in range(self.num_of_base)]
        est_join_sel = [est_join_card[i]/raw_join_card[i] for i in range(self.num_of_join)]
        self.est_base_sel = est_base_sel
        self.est_join_sel = est_join_sel
        self.est_sel = est_base_sel + est_join_sel

        ## Error information
        err_info_dict = {}
        for i in range(self.num_of_base + self.num_of_pair):

            cur_err_list, cur_err_hist = prepare_error_data(db_name, query_id, sensi_dim=i, max_sel=1.0, 
                                                            rel_error=self.rel_error, div=self.div)
            if cur_err_list == [] and cur_err_hist == []: # Don't need to build err profile for this dimension
                err_info_dict[i] = []
                continue
            cur_kde_list = cal_pdf(cur_err_hist, rel_error=self.rel_error, bandwidth=self.b, naive=self.naive)
            err_info_dict[i] = [cur_err_list, cur_err_hist, cur_kde_list]
        self.err_info_dict = err_info_dict

        ## Plan hints
        cur_plan_list = []
        if self.inst_id != None:
            file = './plan/' + self.on_sample + 'tmp_plan_dict_' + self.db_name + '_' + self.query_id + '_' + str(self.inst_id) + self.cal_sen_method + '.txt'
        else:
            file = './plan/' + self.on_sample + 'tmp_plan_dict_' + self.db_name + '_' + self.query_id + self.cal_sen_method +'.txt'
            
            if self.db_name == 'imdbloadbase': # use the plan generated by full err profile (no train-test split)
                file = './plan/' + self.on_sample + 'saved-tmp_plan_dict_' + self.db_name + '_' + self.query_id + self.cal_sen_method +'.txt'
        plan_hint_dict = json.load(open(file))        
        for i in plan_hint_dict.values():
            cur_plan_list = cur_plan_list + i
        cur_plan_list = list(sorted(set(cur_plan_list)))
        # if query_id == '17a':
        #     cur_plan_list = [cur_plan_list[7], cur_plan_list[8], cur_plan_list[10], cur_plan_list[44]]
        self.cur_plan_list = cur_plan_list  # all current plan hints

        ### Get original optimal and robusdt plans
        conn = psycopg2.connect(host="/tmp", dbname=self.db_name, user="lsh") # what database should be used
        conn.set_session(autocommit=True)
        cursor = conn.cursor()
        write_to_file(self.est_base_sel, file_of_base_sel)
        write_to_file(self.est_join_sel, file_of_join_sel)
        write_pointers_to_file(list(range(self.num_of_base + self.num_of_join)))
        cost_of_all_hints = get_all_plan_cost(cursor, self.sql, EXPLAIN, self.cur_plan_list)    # Get candidate plan set
        ori_opt_plan_id = cost_of_all_hints.index(min(cost_of_all_hints))   # original optimal plan
        rob_plan_id = self.rob_plan_dict[self.query_id] # Get robust plan
        self.plan_list = [ori_opt_plan_id] + rob_plan_id[:1]
        self.plan_orders = ["original_plan","robust_plan","adjusted_plan"]
        cursor.close()

        self.center_err = gen_center_from_err_dist(self.est_card, self.raw_card, self.num_of_all_basic, self.err_info_dict, num_of_samples=1000, naive=self.naive)
        self.inject = None

    def get_error_data(self, dim):
        '''Prepare the error data for error distribution at a given dimension
        '''
        data = None
        plotable = False
        error = None
        point_injected = None
        if dim in self.err_files_dict[get_pure_q_id(self.query_id, self.db_name)]:
            plotable = True
            r = find_bin_id_from_err_hist_list(self.est_card, self.raw_card, cur_dim=dim, err_info_dict=self.err_info_dict)
            kde = self.err_info_dict[dim][2][r]
            error = [_[1] for _ in self.err_info_dict[dim][1][r]] # (est_sel, rel_err)
            error = np.array(error).reshape(-1, 1)
            x = np.linspace(min(-5, np.min(error) - 2), max(5, np.max(error) + 2), 1000)[:, np.newaxis]
            y = np.exp(kde.score_samples(x)).tolist()
            x = x[:, 0].tolist()
            data = {"x":x, "y":y}

            error = error[:, 0].tolist()
            error_card = []
            for err in error:
                est_sel = self.est_sel[dim]
                tru_sel = cal_rel_selectivity(err, est_sel)
                tru_card = tru_sel * self.raw_card[dim]
                error_card.append(int(tru_card))
            error = {"error": error, "error_card": error_card}

            if self.inject:
                dim_name = self.dim_id2name_dict[dim]
                if dim_name in self.inject:
                    tru_sel = float(self.inject[dim_name])
                    tru_err = cal_rel_error(tru_sel, self.est_sel[dim])
                    tru_card = tru_sel * self.raw_card[dim]
                    point_injected = {"error": tru_err, "error_card": int(tru_card)}
        return plotable, data, error, point_injected

    def get_basic_info(self, save=False):
        '''Pack the basic information for each dimension
        '''
        basic_info = {}
        for dim, dim_name in self.dim_id2name_dict.items():
            isedge = dim>=self.num_of_base
            if not isedge:
                component = [dim_name]
            else:
                component = dim_name.split('-')
            plottable, error_plot, error, point_injected = self.get_error_data(dim)
            
            # yang: original value
            cardinality = int(self.est_card[dim])
            raw_cardinality = int(self.raw_card[dim])
            selectivity = float(self.est_sel[dim])
        
            dim_info = {
                "dim": dim,
                "isedge": isedge,
                "component": component,
                "cardinality": cardinality,
                "raw_cardinality": raw_cardinality,
                "selectivity": selectivity,
                "cardinality_formatted": f"{int(cardinality):,}",
                "raw_cardinality_formatted": f"{int(raw_cardinality):,}",
                "plottable": plottable,
                "error_plot": error_plot,
                "error": error,
                "point_injected": point_injected
            }
            basic_info[dim_name] = dim_info
        if save:
            with open(f'./demo_data/basic_stats_{self.db_name}_{self.query_id}.json', 'w') as file:
                json.dump(basic_info, file, indent=1)
        # print(json.dumps(basic_info, indent=1))
        return basic_info, json.dumps(basic_info, indent=1)

    def get_sensitive_dim(self, save=False):
        '''Return all sensitive dimensions
        '''
        sen_info = {}
        for rank, dim in enumerate(self.sen_dims):
            dim_name = self.dim_id2name_dict[dim]
            isedge = dim>=self.num_of_base
            if not isedge:
                component = [dim_name]
            else:
                component = dim_name.split('-')
            dim_info = {
                "dim": dim,
                # "rank": rank,
                "isedge": isedge,
                "component": component,
            }
            # print(dim_info)
            sen_info[dim_name] = dim_info
        if save:
            with open(f'./demo_data/sensitive_{self.db_name}_{self.query_id}.json', 'w') as file:
                json.dump(sen_info, file, indent=1)
        return sen_info, json.dumps(sen_info, indent=1)

    def get_cost_info(self):
        '''Return the latency and cost of the plans
        '''
        t1 = time.perf_counter()
        conn = psycopg2.connect(host="/tmp", dbname=self.db_name, user="lsh") # what database should be used
        conn.set_session(autocommit=True)
        cursor = conn.cursor()
        cost_info = {"robust_plan":[]}

        if not self.inject: # There is no user input
            ### Set up for query execution
            write_to_file(self.est_base_sel, file_of_base_sel)
            write_to_file(self.est_join_sel, file_of_join_sel)
            write_pointers_to_file(list(range(self.num_of_base + self.num_of_join)))

            for i, hint_id in enumerate(self.plan_list):
                hint = self.cur_plan_list[hint_id]
                cost = get_plan_cost(cursor, self.sql, hint=hint, explain=EXPLAIN)
                info = [{"cost":cost}]
                if i == 0:
                    cost_info["original_plan"] = info
                else:
                    cost_info["robust_plan"] += info
            self.cost_info = cost_info
        else:   # There is user input
            cost_info = self.cost_info
            self.inject_input_sel()
            cost, join_order, scan_mtd = get_plan_cost(cursor, self.sql, explain=EXPLAIN, debug=True)
            self.adj_plan_hint = gen_final_hint(join_order, scan_mtd)   # get the adjusted plan
            info = [{"cost":cost}]
            cost_info["adjusted_plan"] = info

            # ### After apply the input to db, calculate the cost again
            # for i, hint_id in enumerate(self.plan_list):
            #     hint = self.cur_plan_list[hint_id]
            #     self.inject_input_sel()
            #     cost = get_plan_cost(cursor, self.sql, hint=hint, explain=EXPLAIN)
            #     info = [{"cost":cost}]
            #     if i == 0:
            #         cost_info["original_plan"] = info
            #     else:
            #         cost_info["robust_plan"] += info
        cursor.close()
        t2 = time.perf_counter()
        print(f"get_cost_info:{t2-t1}s")

        cost_info = {key:cost_info[key] for key in self.plan_orders if key in cost_info}   # reorder
        return cost_info, json.dumps(cost_info, indent=1)

    def get_latency_info(self):
        '''Return the latency and cost of the plans
        '''
        t1 = time.perf_counter()
        latency_info = {"robust_plan":[]}


        if not self.inject:
            ### Set up for query execution
            write_to_file(self.est_base_sel, file_of_base_sel)
            write_to_file(self.est_join_sel, file_of_join_sel)
            write_pointers_to_file(list(range(self.num_of_base + self.num_of_join)))

            for i, hint_id in enumerate(self.plan_list):
                hint = self.cur_plan_list[hint_id]
                print(self.sql)
                latency = get_real_latency(self.db_name, self.sql, hint=hint, times=TIMES)
                info = [{"latency":latency}]
                if i == 0:
                    latency_info["original_plan"] = info
                else:
                    latency_info["robust_plan"] += info
            
            self.latency_info = latency_info
        else:
            # print(self.inject)
            latency_info = self.latency_info
            self.inject_input_sel()
            latency = get_real_latency(self.db_name, self.sql, hint=self.adj_plan_hint, times=TIMES)    # MUST use the adjusted plan
            info = [{"latency":latency}]
            latency_info["adjusted_plan"] = info
            print(latency_info)
        t2 = time.perf_counter()
        print(f"get_latency_info:{t2-t1}s")
        
        latency_info = {key:latency_info[key] for key in self.plan_orders if key in latency_info}   # reorder
        return latency_info, json.dumps(latency_info, indent=1)

    def get_act_sel(self, dim_name):
        t1 = time.perf_counter()
        if "-" not in dim_name:
            sub_query = gen_sub_query([dim_name], self.sql)
            sub_query_full = gen_sub_query([dim_name], self.sql, full=True)
            sels = cal_local_selectivity(sub_query, sub_query_full)
        else:
            dims = dim_name.split('-')
            full_join, simple = get_all_join(dims, self.sql)
            print(full_join, simple)
            if simple:
                sub_query_join = gen_sub_query(full_join, self.sql)
                sub_query_left = gen_sub_query([full_join[0]], self.sql)
                sub_query_right = gen_sub_query([full_join[1]], self.sql)
                sels = cal_join_selectivity(sub_query_join, sub_query_left, sub_query_right, -1)
            else:
                sels,count=np.array([0,0],dtype=np.float64),0
                left, right = full_join
                if type(left) == str:
                    sub_query_join = gen_sub_query([left, dims[1]], self.sql)
                    sub_query_left = gen_sub_query([left], self.sql)
                    sub_query_right = gen_sub_query([dims[1]], self.sql)
                    # print("right one way")
                    # print(sub_query_join)
                    # print(sub_query_left)
                    # print(sub_query_right)
                    sels += np.array(cal_join_selectivity(sub_query_join, sub_query_left, sub_query_right, -1))
                    count += 1
                else:
                    for tables in left:
                        sub_query_join = gen_sub_query(tables+[dims[1]], self.sql)
                        sub_query_left = gen_sub_query(tables, self.sql)
                        sub_query_right = gen_sub_query([dims[1]], self.sql)
                        # print("left two way")
                        # print(sub_query_join)
                        # print(sub_query_left)
                        # print(sub_query_right)
                        print(np.array(cal_join_selectivity(sub_query_join, sub_query_left, sub_query_right, -1)))
                        sels += np.array(cal_join_selectivity(sub_query_join, sub_query_left, sub_query_right, -1))
                        count += 1
                if type(right) == str:
                    sub_query_join = gen_sub_query([dims[0], right], self.sql)
                    sub_query_left = gen_sub_query([dims[0]], self.sql)
                    sub_query_right = gen_sub_query([right], self.sql)
                    # print("right one way")
                    # print(sub_query_join)
                    # print(sub_query_left)
                    # print(sub_query_right)
                    sels += np.array(cal_join_selectivity(sub_query_join, sub_query_left, sub_query_right, -1))
                    count += 1
                else:
                    for tables in right:
                        sub_query_join = gen_sub_query([dims[0]]+tables, self.sql)
                        sub_query_left = gen_sub_query([dims[0]], self.sql)
                        sub_query_right = gen_sub_query(tables, self.sql)
                        # print("right two way")
                        # print(sub_query_join)
                        # print(sub_query_left)
                        # print(sub_query_right)
                        sels += np.array(cal_join_selectivity(sub_query_join, sub_query_left, sub_query_right, -1))
                        count += 1
                sels /= count
        act_sel, est_sel = sels[0], sels[1]
        # print(act_sel, est_sel)
        t2 = time.perf_counter()
        print(f"get_act_sel:{t2-t1}")
        return act_sel

    def rqo(self, save=False):
        '''Get plans under rqo algo. If user-input selectivity is provided, add an additional plan with input injected.
        '''
        t1 = time.perf_counter()
        ### Connect ot postgres server
        conn = psycopg2.connect(host="/tmp", dbname=self.db_name, user="lsh") # what database should be used
        conn.set_session(autocommit=True)
        cursor = conn.cursor()

        plans = []
        for hint_id in self.plan_list:
            hint = self.cur_plan_list[hint_id]
            _, plan = get_plan_cost(cursor, self.sql, hint=hint, explain=EXPLAIN_ALL, plan=True)
            plans.append(plan)
        if self.inject:
            ### Inject the user's inputs
            self.inject_input_sel()
            _, plan = get_plan_cost(cursor, self.sql, explain=EXPLAIN_ALL, plan=True)
            plans += [plan]
        cursor.close()

        if save:
            with open(f'./demo_data/plans_{self.db_name}_{self.query_id}.json', 'w') as file:
                json.dump(plans, file, indent=1)
        t2 = time.perf_counter()
        print(f"rqo():{t2-t1}s")
        return plans, json.dumps(plans, indent=1)

    def inject_input_sel(self, inject=None, sel=True, sample=False):
        '''Process and inject the user input into postgres
        '''
        if not inject or (inject and sample):
            if not inject:
                inject = self.inject
            error = []
            rel_list = []
            for dim_name, sel_adj in inject.items():
                dim = self.dim_name2id_dict[dim_name]
                rel_list.append(dim)
                if sel:
                    est_sel = self.est_sel[dim]
                    err = cal_rel_error(float(sel_adj), est_sel)
                else:
                    err = float(sel_adj)
                error.append(err)
            _, _ = prep_sel(self.dim_name2id_dict, self.join_map, self.join_info,
                            self.est_base_sel, file_of_base_sel,
                            self.est_join_sel, file_of_join_sel,
                            error=error, recentered_error=self.center_err,
                            relation_list=rel_list, rela_error=self.rel_error)
        else:
            self.inject = inject

    def gen_samples_from_joint_err_dist(self, N, random_seeds=True, naive=False):
        ''' Generate samples from the error distribution on each dimension and then joint them
        '''
        t1 = time.perf_counter()
        if random_seeds:
            np.random.seed(2023)
        joint_error_samples = []
        for table_id in self.sen_dims:
            if naive:
                err_sample = np.random.uniform(-10, 10, N)
            else:
                r = find_bin_id_from_err_hist_list(self.est_card, self.raw_card, cur_dim=table_id, err_info_dict=self.err_info_dict)
                pdf_of_err = self.err_info_dict[table_id][2][r]
                err_sample = pdf_of_err.sample(N)
            joint_error_samples.append(err_sample)
        ### Transfer to joint samples
        if naive:
            joint_error_samples = np.array(joint_error_samples).T.tolist()
        else:
            joint_error_samples = np.array(joint_error_samples).T.tolist()[0]
        t2 = time.perf_counter()
        print(f"gen_samples_from_joint_err_dist:{t2-t1}")
        return joint_error_samples

    def get_all_cost(self, N=100, save=False):
        t1 = time.perf_counter()
        if self.plan_list:
            costs = []
            ### Connect ot postgres server
            conn = psycopg2.connect(host="/tmp", dbname=self.db_name, user="lsh") # what database should be used
            conn.set_session(autocommit=True)
            cursor = conn.cursor()
            error_samples = self.gen_samples_from_joint_err_dist(N, naive=self.naive)
            for i, plan_id in enumerate(self.plan_list):
                plan_costs = {}
                hint = self.cur_plan_list[plan_id]
                for j, dim in enumerate(self.sen_dims):
                    dim_name = self.dim_id2name_dict[dim]
                    x, y = [], []
                    dim_cost = []
                    est_sel = self.est_sel[dim]
                    for sample in tqdm(error_samples):
                        sample_inject = {dim_name:sample[j]}
                        self.inject_input_sel(sample_inject, sel=False, sample=True)
                        cost = get_plan_cost(cursor, self.sql, hint=hint, explain=EXPLAIN)

                        ### Convert error to selectivity
                        err = sample[j]
                        tru_sel = cal_rel_selectivity(err, est_sel)

                        dim_cost.append((tru_sel, cost))
                    dim_cost = sorted(dim_cost, key=lambda t:t[0])
                    for s, c in dim_cost:
                        x.append(s)
                        y.append(c)
                    plan_costs[dim_name] = {"x":x, "y":y}

                costs.append(plan_costs)
                print(f"plans: {i+1}/{len(self.plan_list)} done.")
            self.costs = costs
                
            if save:
                with open(f'./demo_data/costs_{self.db_name}_{self.query_id}.json', 'w') as file:
                    json.dump(costs, file, indent=1)
            t2 = time.perf_counter()
            print(f"get_all_cost:{t2-t1}")
            return costs, json.dumps(costs, indent=1)
        # else:pass

    def get_all_cost_2d(self, N=10, save=False):
        t1 = time.perf_counter()
        costs = []
        ### Connect ot postgres server
        conn = psycopg2.connect(host="/tmp", dbname=self.db_name, user="lsh") # what database should be used
        conn.set_session(autocommit=True)
        cursor = conn.cursor()

        ### Sample all error data
        error_samples = self.gen_samples_from_joint_err_dist(N, naive=self.naive)
        ### Generate all pairs of sensitive dims
        dim_pairs = list(combinations(range(len(error_samples[0])), 2))

        for j, plan_id in enumerate(self.plan_list):
            plan_costs = []
            hint = self.cur_plan_list[plan_id]
            # print(plan_id)
            # print(hint)

            ### For each pair of sen_dims
            for pair in dim_pairs:
                dims = [self.sen_dims[idx] for idx in pair]
                dim_names = [self.dim_id2name_dict[dim] for dim in dims]
                est_sels = [self.est_sel[dim] for dim in dims]

                samples_product = product(*[[sample[idx] for sample in error_samples] for idx in pair])
                dim_cost = []
                for sample in tqdm(samples_product):
                    sample_inject = {dim_names[i]:sample[i] for i in range(len(dims))}
                    self.inject_input_sel(sample_inject, sel=False, sample=True)
                    cost = get_plan_cost(cursor, self.sql, hint=hint, explain=EXPLAIN)
                    p = cal_prob_of_sample(sample, dims, self.est_card, self.raw_card, self.err_info_dict, True)
                    ### Convert error to selectivity
                    sels = []
                    for i in range(len(dims)):
                        err = sample[i]
                        est_sel = est_sels[i]
                        tru_sel = cal_rel_selectivity(err, est_sel)
                        sels.append(tru_sel)
                    
                    dim_cost.append((sels, cost, p))

                dim_cost = sorted(dim_cost, key=lambda t:(t[0][0], t[0][1]))
                xy, z = [], []
                prob = []
                for s, c, p in dim_cost:
                    xy.append(s)
                    z.append(c)
                    prob.append(p)
                plan_costs.append({"dim1":dim_names[0].replace('-', ' ⨝ '), "dim2":dim_names[1].replace('-', ' ⨝ '), "xy":xy, "z":z, "prob": prob})

            costs.append(plan_costs)
            print(f"plans: {j+1}/{len(self.plan_list)} done.")
        self.costs = costs
            
        if save:
            with open(f'./demo_data/costs_2d_{self.db_name}_{self.query_id}.json', 'w') as file:
                json.dump(costs, file, indent=1)
        t2 = time.perf_counter()
        print(f"get_all_cost_2d:{t2-t1}")
        return costs, json.dumps(costs, indent=1)

if __name__ == "__main__":
    query_id = "1a"
    save = True
    demo = Demo(query_id=query_id)
    basic_stats, basic_stats_json = demo.get_basic_info(save=save)
    
    # sen_dims, sen_dims_json = demo.get_sensitive_dim()
    # print(sen_dims)

    # plans, plans_json = demo.rqo(save=save)
    
    inject = {"mi_idx-it":0.1}  # 1a
    # inject = {"mc-cn":0.1}  # 2a
    demo.inject_input_sel(inject=inject)
    print(demo.inject)
    basic_stats, basic_stats_json = demo.get_basic_info(save=save)
    # plans_adj, plans_adj_json = demo.rqo(save=save)

    # demo.get_act_sel('mi_idx-t')

    # demo.get_all_cost_2d(save=save)