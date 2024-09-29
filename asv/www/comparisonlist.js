'use strict';

$(document).ready(function() {
    /* The state of the parameters in the sidebar.  Dictionary mapping
       strings to values determining the "enabled" configurations. */
    var state = null;
    /* Cache of constructed tables, {data_path: table_dom_id} */
    var table_cache = {};
    var table_cache_counter = 0;

    function setup_display(state_selection) {
        var new_state = setup_state(state_selection);
        var same_state = (state !== null);

        /* Avoid needless UI updates, e.g., on table sort */

        if (same_state) {
            $.each(state, function (key, value) {
                if (value != new_state[key]) {
                    same_state = false;
                }
            });
        }

        if (!same_state) {
            state = new_state;

            $("#comparisonlist-body table").hide();
            $("#comparisonlist-body .message").remove();

            if (table_cache['comparisonlist'] !== undefined) {
                $(table_cache['comparisonlist']).show();
            }
            else {
                $("#comparisonlist-body").append($("<p class='message'>Loading...</p>"));
                $.ajax({
                    url: "comparison.json",
                    dataType: "json",
                    cache: true
                }).done(function (data) {
                    var table = construct_machines_comparison_benchmark_table(data);
                    var table_name = 'comparisonlist-table-' + table_cache_counter;
                    ++table_cache_counter;
    
                    table.attr('id', table_name);
                    table_cache['comparisonlist'] = '#' + table_name;
                    $("#comparisonlist-body .message").remove();
                    $("#comparisonlist-body").append(table);
                    table.show();         
                });
            }
        }
    }

    function update_state_url(key, value) {
        var info = $.asv.parse_hash_string(window.location.hash);
        var new_state = get_valid_state(state, key, value);

        $.each($.asv.master_json.params, function(param, values) {
            if (values.length > 1) {
                info.params[param] = [new_state[param]];
            }
            else if (info.params[param]) {
                delete info.params[param];
            }
        });

        window.location.hash = $.asv.format_hash_string(info);
    }

    function obj_copy(obj) {
        var newobj = {};
        $.each(obj, function(key, val) {
            newobj[key] = val;
        });
        return newobj;
    }

    function obj_diff(obj1, obj2) {
        var count = 0;
        $.each(obj1, function(key, val) {
            if (obj2[key] != val) {
                ++count
            }
        });
        return count;
    }

    function get_valid_state(tmp_state, wanted_key, wanted_value) {
        /*
          Get an available state with wanted_key having wanted_value,
          preferably as a minor modification of tmp_state.
         */
        var best_params = null;
        var best_diff = 1e99;
        var best_hit = false;

        tmp_state = obj_copy(tmp_state);
        if (wanted_key !== undefined) {
            tmp_state[wanted_key] = wanted_value;
        }

        $.each($.asv.master_json.graph_param_list, function(idx, params) {
            var diff = obj_diff(tmp_state, params);
            var hit = (wanted_key === undefined || params[wanted_key] == wanted_value);

            if ((!best_hit && hit) || (hit == best_hit && diff < best_diff)) {
                best_params = params;
                best_diff = diff;
                best_hit = hit;
            }
        });

        if (best_params === null) {
            best_params = $.asv.master_json.graph_param_list[0];
        }

        return obj_copy(best_params);
    }

    function setup_state(state_selection) {
        var index = $.asv.master_json;
        var state = {};

        state.machine = index.params.machine;

        $.each(index.params, function(param, values) {
            state[param] = values[0];
        });

        if (state_selection !== null) {
            /* Select a specific generic parameter state */
            $.each(index.params, function(param, values) {
                if (state_selection[param]) {
                    state[param] = state_selection[param][0];
                }
            });
        }

        return get_valid_state(state);
    }

    function construct_machines_comparison_benchmark_table(data) {
        var index = $.asv.master_json;

        var table = $('<table class="table table-hover"/>');

        /* Form a new table */
        var machines = data.machines;
        var benchmarks = data.benchmarks;
        var average = data.average;
        var baseline_machine = data.baseline;

        var second_row = $('<tr/>');
        var total = $('<td class="stats"/>');
        total.text('Total number of benchmarks: ' + benchmarks.length);
        second_row.append(total);
        var machines_head = '';
        $.each(machines, function(machine_idx, machine) {
            machines_head += '<th data-sort="float">' + machine + '</th>'
            var percent = $('<td class="stats"/>');
            if (average !== undefined) {
                percent.append(average[machine_idx].toFixed(2) + '%');
                second_row.append(percent);
            }
            
        });
        var table_head = $('<thead><tr>' +
                           '<th data-sort="string">Benchmark</th>' + machines_head +
                           '</tr></thead>');
        table.append(table_head);

        var table_body = $('<tbody/>');
        if (average !== undefined) {
            table_body.append(second_row);
        } else {
            baseline_machine = -1;
        }


        $.each(benchmarks, function(row_idx, row) {
            var tr = $('<tr/>');
            var name_td = $('<td/>');
            var name = $('<a/>');
            var benchmark_url_args = {};
            var benchmark_full_url;
            var benchmark_base_url;

            /* Format benchmark url */
            benchmark_url_args.location = [row.name];
            benchmark_url_args.params = {};
            $.each($.asv.master_json.params, function (key, values) {
                if (values.length > 1) {
                    benchmark_url_args.params[key] = [state[key]];
                }
            });
            benchmark_base_url = $.asv.format_hash_string(benchmark_url_args);
            if (row.idx !== null) {
                var benchmark = $.asv.master_json.benchmarks[row.name];
                $.each($.asv.param_selection_from_flat_idx(benchmark.params, row.idx).slice(1),
                       function(i, param_values) {
                           benchmark_url_args.params['p-'+benchmark.param_names[i]]
                               = [benchmark.params[i][param_values[0]]];
                       });
            }
            benchmark_full_url = $.asv.format_hash_string(benchmark_url_args);

            /* Benchmark name column */
            var bm_link;
            if (row.idx === null) {
                bm_link = $('<a/>').attr('href', benchmark_base_url).text(row.pretty_name);
                name_td.append(bm_link);
            }
            else {
                var basename = row.pretty_name;
                var args = null;
                var m = row.pretty_name.match(/(.*)\(.*$/);
                if (m) {
                    basename = m[1];
                    args = row.pretty_name.slice(basename.length);
                }
                bm_link = $('<a/>').attr('href', benchmark_base_url).text(basename);
                name_td.append(bm_link);
                if (args) {
                    var bm_idx_link;
                    var graph_url;
                    bm_idx_link = $('<a/>').attr('href', benchmark_full_url).text(' ' + args);
                    name_td.append(bm_idx_link);
                    graph_url = $.asv.graph_to_path(row.name, state);
                    $.asv.ui.hover_graph(bm_idx_link, graph_url, row.name, row.idx, null);
                }
            }
            $.asv.ui.hover_summary_graph(bm_link, row.name);
            tr.append(name_td);

            /* Values column */
            $.each(machines, function(machine_idx, machine) {
                var last_value = row.last_value[machine_idx];
                var last_err = row.last_err[machine_idx];
                var value_class = "value";
                if (row.best === machine_idx) {
                    value_class = "value-best";
                } else if (row.worst === machine_idx) {
                    value_class = "value-worst";
                }
                var value_td = $('<td class="' + value_class + '"/>');
                if (last_value !== null) {
                    var value, err, err_str, sort_value;
                    var unit = $.asv.master_json.benchmarks[row.name].unit;
                    value = $.asv.pretty_unit(last_value, unit);
                    if (unit == "seconds") {
                        sort_value = last_value * 1e100;
                    }
                    else {
                        sort_value = last_value;
                    }
                    var baseline_percent = '';
                    if (baseline_machine !== -1 && baseline_machine !== machine_idx) {
                        baseline_percent = ' (' + row.cmp_percent[machine_idx].toFixed(2) + '%)';
                    }
                    var value_span = $('<span/>').text(value + baseline_percent);

                    err = 100*last_err/last_value;
                    if (err == err) {
                        err_str = " \u00b1 " + err.toFixed(0.1) + '%';
                    }
                    else {
                        err_str = "";
                    }
                    value_span.attr('data-toggle', 'tooltip');
                    value_span.attr('title', value + err_str);
                    value_td.append(value_span);
                    value_td.attr('data-sort-value', sort_value);
                }
                else {
                    value_td.attr('data-sort-value', -1e99);
                }
                tr.append(value_td);
            });
            table_body.append(tr);
        });

        table_body.find('[data-toggle="tooltip"]').tooltip();

        /* Finalize */
        table.append(table_body);
        // setup_sort(table);

        return table;
    }

    function setup_sort(table) {
        var info = $.asv.parse_hash_string(window.location.hash);

        table.stupidtable();

        table.on('aftertablesort', function (event, data) {
            var info = $.asv.parse_hash_string(window.location.hash);
            info.params['sort'] = [data.column];
            info.params['dir'] = [data.direction];
            window.location.hash = $.asv.format_hash_string(info);

            /* Update appearance */
            table.find('thead th').removeClass('asc');
            table.find('thead th').removeClass('desc');
            var th_to_sort = table.find("thead th").eq(parseInt(data.column));
            if (th_to_sort) {
                th_to_sort.addClass(data.direction);
            }
        });

        if (info.params.sort && info.params.dir) {
            var th_to_sort = table.find("thead th").eq(parseInt(info.params.sort[0]));
            th_to_sort.stupidsort(info.params.dir[0]);
        }
        else {
            var th_to_sort = table.find("thead th").eq(0);
            th_to_sort.stupidsort("asc");
        }
    }

    /*
     * Entry point
     */
    $.asv.register_page('comparisonlist', function(params) {
        var state_selection = null;

        if (Object.keys(params).length > 0) {
            state_selection = params;
        }

        setup_display(state_selection);

        $('#comparisonlist-display').show();
        $("#title").text("List of benchmarks");
    });
});
