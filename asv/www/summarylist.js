'use strict';

$(document).ready(function() {
    /* The state of the parameters in the sidebar.  Dictionary mapping
       strings to values determining the "enabled" configurations. */
    var state = null;

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
            replace_params_ui();

            var filename = $.asv.graph_to_path('summary', state);
            $.asv.load_graph_data(
                filename
            ).done(function (data) {
                replace_benchmark_table(data);
            });
        }
    }

    function update_state_url(key, value) {
        var info = $.asv.parse_hash_string(window.location.hash);
        $.each($.asv.master_json.params, function(param, values) {
            if (values.length > 1) {
                info.params[param] = [state[param]];
            }
            else if (info.params[param]) {
                delete info.params[param];
            }
        });
        info.params[key] = [value];
        window.location.hash = $.asv.format_hash_string(info);
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

        return state;
    }

    function replace_params_ui() {
        var index = $.asv.master_json;

        var nav = $('#summarylist-navigation');
        nav.empty();
        
        /* Machine selection */
        $.asv.ui.make_value_selector_panel(nav, 'machine', index.params.machine,  function(i, machine, button) {
            button.text(machine);

            button.on('click', function(evt) {
                update_state_url('machine', machine);
            });

            if (state.machine != machine) {
                button.removeClass('active');
            }
            button.removeAttr('data-toggle');

            /* Create tooltips for each machine */
            var details = [];
            $.each(index.machines[machine], function(key, val) {
                details.push(key + ': ' + val);
            });
            details = details.join('<br/>');

            button.tooltip({
                title: details,
                html: true,
                placement: 'right',
                container: 'body',
                animation: false
            });
        });

        /* Generic parameter selectors */
        $.each(index.params, function(param, values) {
            if (values.length > 1 && param != 'machine') {
                $.asv.ui.make_value_selector_panel(nav, param, values, function(i, value, button) {
                    var value_display;
                    if (value === null)
                        value_display = '[none]';
                    else if (!value)
                        value_display = '[default]';
                    else
                        value_display = value;

                    button.text(value_display);

                    if (state[param] != value) {
                        button.removeClass('active');
                    }

                    button.on('click', function(evt) {
                        update_state_url(param, value);
                    });
                });
            }
        });

        $(nav).find(".btn-group").removeAttr("data-toggle");

        $.asv.ui.reflow_value_selector_panels();
    }

    function replace_benchmark_table(data) {
        var index = $.asv.master_json;
        var body = $("#summarylist-body");

        body.empty();

        /* Form a new table */

        var table = $('<table class="table table-hover"/>');

        var table_head = $('<thead><tr>' +
                           '<th data-sort="string">Benchmark</th>' +
                           '<th data-sort="value">Value</th>' +
                           '<th data-sort="factor">Recent change</th>' +
                           '<th data-sort="string">Changed at</th>' +
                           '</tr></thead>');
        table.append(table_head);

        var table_body = $('<tbody/>');

        $.each(data, function(row_idx, row) {
            var tr = $('<tr/>');
            var name_td = $('<td/>');
            var name = $('<a/>');
            var url = '#/' + row.name;
	    var benchmark_full_url;

            if (row.idx === null) {
                name_td.append($('<a/>').attr('href', url).text(row.pretty_name));
		benchmark_full_url = url + '?';
            }
            else {
                var basename = row.pretty_name;
                var args = null;
                var m = row.pretty_name.match(/(.*)\(.*$/);
                if (m) {
                    basename = m[1];
                    args = row.pretty_name.slice(basename.length);
                }
                name_td.append($('<a/>').attr('href', url).text(basename));
                if (args) {
                    name_td.append($('<a/>').attr('href', url + '?idx=' + row.idx).text(' ' + args));
                }
		benchmark_full_url = url + '?idx=' + row.idx;
            }

            var value_td = $('<td class="value"/>');
            if (row.last_value !== null) {
                var value, err, err_str;
                if ($.asv.master_json.benchmarks[row.name].unit == "seconds") {
                    value = $.asv.pretty_second(row.last_value);
                }
                else {
                    value = row.last_value.toPrecision(3);
                }
                err = 100*row.last_err/row.last_value;
                if (err == err) {
                    err_str = " \u00b1 " + err.toFixed(0.1) + '%';
                }
                else {
                    err_str = "";
                }
                value_td.append($('<span/>').text(value + err_str));
            }

            var change_td = $('<td class="change"/>');
            if (row.prev_value !== null) {
                var text, change_str, change = 0;
                if ($.asv.master_json.benchmarks[row.name].unit == "seconds") {
                    change_str = $.asv.pretty_second(row.last_value - row.prev_value);
                }
                else {
                    change_str = '' + (row.last_value - row.prev_value).toPrecision(3);
                }
                if (!change_str.match(/^-/)) {
                    change_str = '+' + change_str;
                }
                if (row.prev_value != 0) {
                    change = 100 * (row.last_value / row.prev_value - 1);
                    text = change.toFixed(1) + '%  (' + change_str + ')';
                    if (change > 0) {
                        text = '+' + text;
                    }
                }
                else {
                    text = ' (' + change_str + ')';
                }
                text = text.replace('-', '\u2212');
                change_td.append($('<a/>').attr('href', benchmark_full_url
						+ '&commits='
						+ $.asv.master_json.revision_to_hash[row.change_rev]
					       ).text(text));
                if (change > 5) {
                    change_td.addClass('positive-change');
                }
                else if (change < -5) {
                    change_td.addClass('negative-change');
                }
            }

            var changed_at_td = $("<td/>");
            if (row.change_rev !== null) {
                var date = new Date($.asv.master_json.revision_to_date[row.change_rev]);
                var commit = $.asv.get_commit_hash(row.change_rev);
                var commit_a = $('<a/>');
                var last_commit = $.asv.get_commit_hash(row.last_rev);
                var last_commit_a = $('<a/>');
                var span = $('<span/>');
                commit_a.attr('href', $.asv.master_json.show_commit_url + commit);
                commit_a.text(commit);
                last_commit_a.attr('href', $.asv.master_json.show_commit_url + commit);
                last_commit_a.text(commit);
                span.text(' (' + date.toISOString() + ')');
                span.prepend(commit_a);
                changed_at_td.append(span);
            }

            tr.append(name_td);
            tr.append(value_td);
            tr.append(change_td);
            tr.append(changed_at_td);

            table_body.append(tr);
        });

        /* Finalize */
        table.append(table_body);
        setup_sort(table);
        body.append(table);
    }

    function setup_sort(table) {
        var info = $.asv.parse_hash_string(window.location.hash);

        table.stupidtable({
            'value': function(a, b) {
                function key(s) {
                    for (var k = 0; k < $.asv.time_units.length; ++k) {
                        var entry = $.asv.time_units[k];
                        var m = s.match('^([0-9.]+)' + entry[0] + ' .*');
                        if (m) {
                            return parseFloat(m[1]) * entry[2] * 1e-30;
                        }
                    }
                    return parseFloat(s.replace(/\u00b1.*/, ''));
                }
                return key(a) - key(b)
            },
            'factor': function(a, b) {
                var val_a = a.replace(/x/, '').replace(/\u2212/, '-').replace(/\(.*/, '');
                var val_b = b.replace(/x/, '').replace(/\u2212/, '-').replace(/\(.*/, '');
                if (!val_a) {
                    val_a = '0';
                }
                if (!val_b) {
                    val_b = '0';
                }
                return parseFloat(val_a) - parseFloat(val_b);
            }
        });

        table.bind('aftertablesort', function (event, data) {
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
    $.asv.register_page('summarylist', function(params) {
        var state_selection = null;

        if (Object.keys(params).length > 0) {
            state_selection = params;
        }

        setup_display(state_selection);

        $('#summarylist-display').show();
        $("#title").text("List of benchmarks");
    });
});
