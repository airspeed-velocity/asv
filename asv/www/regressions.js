'use strict';

$(document).ready(function() {
    /* Cached contents of downloaded regressions.json */
    var regression_data = null;
    /* Current page title */
    var current_title = "Regressions";
    /* Whether HTML5 local storage is available */
    var local_storage_available = false;
    /* Key prefix for ignored regressions. For each ignored regression,
       a key "ignore_key_prefix + md5(benchmark_name + date_a + date_b)"
       is added to HTML5 local storage.
     */
    var ignore_key_prefix = null;
    /* Set of ignored regressions, same information as in HTML5 local storage.
       Useful if local storage runs out of space. */
    var ignored_regressions = {};

    function load_data(params) {
        $("#title").text(current_title);

        if (typeof(Storage) !== "undefined") {
            /* html5 local storage available */
            local_storage_available = true;
        }

        if (regression_data) {
            // already displayed
        }
        else {
            var message = $('<div>Loading...</div>');
            $('#regressions-body').append(message);
            $.ajax({
                url: 'regressions.json',
                cache: false
            }).done(function (data) {
                regression_data = data;
                var main_div = display_data(data, params);
                $('#regressions-body').empty();
                $('#regressions-body').append(main_div);
            });
        }
    }

    function display_data(data, params) {
        var main_div = $('<div/>');
        var branches = $.asv.master_json.params['branch'];
        var all_ignored_keys = {};

        ignore_key_prefix = 'asv-r-' + $.asv.master_json.project;

        if (branches && branches.length > 1) {
            /* Add a branch selector */
            var dropdown_menu = $('<ul class="dropdown-menu" role="menu"/>');
            var dropdown_div = $('<div class="dropdown">');

            dropdown_div.append($('<button class="btn btn-default dropdown-toggle" data-toggle="dropdown">Branches ' + 
                                  '<span class="caret"/></button>'));
            dropdown_div.append(dropdown_menu);

            main_div.append(dropdown_div);
        }

        $.each(branches, function(i, branch) {
            var branch_div = $('<div class="regression-div"/>')

            var display_table = $('<table class="table table-hover"/>');
            var ignored_table = $('<table class="table table-hover ignored"/>');
            var ignored_button = $('<button class="btn btn-default">Show ignored regressions...</button>');

            if (branches && branches.length > 1) {
                var branch_link = $('<a/>')
                branch_link.text(branch);

                dropdown_menu.append($('<li role="presentation"/>').append(branch_link));
                branch_link.on('click', function(evt) {
                    current_title = "Regressions (" + branch + " branch)";
                    $("#title").text(current_title);
                    $(".regression-div").hide();
                    $("table.ignored").hide();
                    ignored_button.show();
                    $("#regression-div-" + i).show();
                    $("#regression-div-" + i + '-ignored').show();
                });
            }
            else {
                branch = null;
            }

            branch_div.attr('id', 'regression-div-' + i);
            branch_div.hide();
            main_div.append(branch_div);

            create_data_table(display_table, ignored_table, data, params, branch, all_ignored_keys);
            branch_div.append(display_table);
            ignored_table.hide();

            if (local_storage_available) {
                branch_div.append(ignored_table);

                branch_div.append(ignored_button);
                ignored_button.on('click', function(evt) {
                    ignored_button.hide();
                    $("table.ignored").show();
                });
            }
        });

        if (branches && branches.length > 1) {
            current_title = "Regressions (" + branches[0] + " branch)";
        }
        $("#title").text(current_title);
        main_div.find("#regression-div-0").show();
        main_div.show();

        if (local_storage_available) {
            /* Clear out local storage space */
            var keys = Object.keys(localStorage);
            $.each(keys, function(i, key) {
                if (key.slice(0, ignore_key_prefix.length) == ignore_key_prefix &&
                        !all_ignored_keys[key]) {
                    delete localStorage[key];
                }
            });
        }

        return main_div;
    }

    function create_data_table(display_table, ignored_table, data, params, branch, all_ignored_keys) {
        var table_head = $('<thead><tr>' +
                           '<th data-sort="string">Benchmark</th>' +
                           '<th data-sort="string">Date</th>' +
                           '<th data-sort="string">Commit(s)</th>' +
                           '<th data-sort="factor">Factor</th>' +
                           '<th data-sort="value">Best</th>' +
                           '<th data-sort="value">Current</th>' +
                           '<th></th>' +
                           '</tr></thead>');

        display_table.append(table_head);
        ignored_table.append(table_head.clone());

        var table_body = $('<tbody/>');
        var ignored_table_body = $('<tbody/>');

        var date_to_hash = data['date_to_hash'];
        var regressions = data['regressions'];

        $.each(regressions, function (i, item) {
            var benchmark_name = item[0];
            var graph_url = item[1];
            var param_dict = item[2];
            var parameter_idx = item[3];
            var regression = item[4];

            if (regression === null) {
                return;
            }

            if (branch !== null && param_dict['branch'] != branch) {
                return;
            }
            var date_a = regression[0];
            var date_b = regression[1];
            var new_value = regression[2];
            var old_value = regression[3];

            var factor = new_value / old_value;
            var commit_a = $.asv.master_json.date_to_hash[date_a];
            var commit_b = $.asv.master_json.date_to_hash[date_b];
            var date_fmt = new Date(date_b);

            var row = $('<tr/>');
            var item;

            var benchmark_basename = benchmark_name.replace(/\(.*/, '');
            var url_params = {};

            $.each(param_dict, function (key, value) {
                url_params[key] = [value];
            });

            url_params.time = [date_b];
            if (date_a) {
                url_params.time.push(date_a);
            }

            if (parameter_idx !== null) {
                url_params.idx = [parameter_idx];
            }
            var benchmark_url = $.asv.format_hash_string({
                location: [benchmark_basename],
                params: url_params
            });

            if ($.asv.master_json.benchmarks[benchmark_basename].unit == "seconds") {
                new_value = $.asv.pretty_second(new_value);
                old_value = $.asv.pretty_second(old_value);
            }
            else {
                new_value = new_value.toPrecision(3);
                old_value = old_value.toPrecision(3);
            }

            var benchmark_link = $('<a/>').attr('href', benchmark_url).text(benchmark_name);
            row.append($('<td/>').append(benchmark_link));
            row.append($('<td/>').text(date_fmt.toISOString()));
            if (commit_a) {
                var td = $('<td/>');
                if ($.asv.master_json.show_commit_url.match(/.*\/\/github.com\//)) {
                    var commit_url = ($.asv.master_json.show_commit_url + '../compare/'
                                      + commit_a + '...' + commit_b);
                    row.append(td.append(
                        $('<a/>').attr('href', commit_url).text(commit_a + '..' + commit_b)));
                }
                else {
                    row.append(td.text(commit_a + '..' + commit_b));
                }
            }
            else {
                var commit_url = $.asv.master_json.show_commit_url + commit_b;
                row.append($('<td/>').append(
                    $('<a/>').attr('href', commit_url).text(commit_b)));
            }
            row.append($('<td/>').text(factor.toFixed(2) + 'x'));
            row.append($('<td/>').text(old_value));
            row.append($('<td/>').text(new_value));

            if (local_storage_available) {
                /* html5 local storage has limited size, so store hashes
                   rather than potentially long strings */
                var ignore_key = ignore_key_prefix + $.md5(benchmark_name + '' + date_a + '' + date_b);
                all_ignored_keys[ignore_key] = 1;

                var is_ignored = (ignore_key in localStorage) || (ignore_key in ignored_regressions);
                var ignore_button = $('<button class="btn btn-small"/>');

                row.attr('id', ignore_key);

                ignore_button.on('click', function(evt) {
                    if (ignore_key in localStorage || ignore_key in ignored_regressions) {
                        delete localStorage[ignore_key];
                        delete ignored_regressions[ignore_key];
                        var item = ignored_table_body.find('#' + ignore_key).detach();
                        ignore_button.text('Ignore');
                        table_body.append(item);
                    }
                    else {
                        try {
                            localStorage[ignore_key] = 1;
                        } catch (err) {
                            /* Out of quota -- we're just going to ignore that */
                        }
                        ignored_regressions[ignore_key] = 1;
                        var item = table_body.find('#' + ignore_key).detach();
                        ignore_button.text('Unignore');
                        ignored_table_body.append(item);
                    }
                });

                row.append($('<td/>').append(ignore_button));

                if (!is_ignored) {
                    ignore_button.text('Ignore');
                    table_body.append(row);
                }
                else {
                    ignore_button.text('Unignore');
                    ignored_table_body.append(row);
                }
            }
            else {
                table_body.append(row);
            }

            /* Show the summary graph as a popup */
            var plot_div = $('<div/>');
            plot_div.css('width', '11.8em');
            plot_div.css('height', '7em');
            plot_div.css('border', '2px solid black');
            plot_div.css('background-color', 'white');

            function update_plot() {
                var markings = [
                    { color: '#d00', lineWidth: 2, xaxis: { from: date_b, to: date_b }}
                ];
                if (date_a !== null) {
                    markings.push({ color: '#d00', lineWidth: 2, xaxis: { from: date_a, to: date_a }});
                    markings.push({ color: "rgba(255,0,0,0.1)", xaxis: { from: date_a, to: date_b }});
                }

                $.ajax({
                    url: graph_url,
                    cache: false
                }).done(function(data) {
                    var params = $.asv.master_json.benchmarks[benchmark_basename].params;
                    data = $.asv.filter_graph_data_idx(data, 0, parameter_idx, params);
                    var options = {
                        colors: ['#000'],
                        series: {
                            lines: {
                                show: true,
                                lineWidth: 2
                            },
                            shadowSize: 0
                        },
                        grid: {
                            borderWidth: 1,
                            margin: 0,
                            labelMargin: 0,
                            axisMargin: 0,
                            minBorderMargin: 0,
                            markings: markings,
                        },
                        xaxis: {
                            ticks: [],
                        },
                        yaxis: {
                            ticks: [],
                            min: 0
                        },
                        legend: {
                            show: false
                        }
                    };
                    var plot = $.plot(plot_div, [{data: data}], options);
                }).fail(function() {
                    // TODO: Handle failure
                })
                return plot_div;
            }
            benchmark_link.popover({
                placement: 'right auto',
                trigger: 'hover',
                html: true,
                delay: 50,
                content: $('<div/>').append(plot_div)
            });
            benchmark_link.on('show.bs.popover', update_plot);
        });

        display_table.append(table_body);
        ignored_table.append(ignored_table_body);

        function setup_sort(table) {
            table.stupidtable({
                'value': function(a, b) {
                    function key(s) {
                        for (var k = 0; k < $.asv.time_units.length; ++k) {
                            var entry = $.asv.time_units[k];
                            m = s.match('^([0-9.]+)'+entry[0]+'$');
                            if (m) {
                                return parseFloat(m[1]) * entry[2] * 1e-30;
                            }
                        }
                        return 0;
                    }
                    return key(a) - key(b)
                },
                'factor': function(a, b) {
                    return parseFloat(a.replace(/x/, '')) - parseFloat(b.replace(/x/, ''));
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

            if (params.sort && params.dir) {
                var th_to_sort = table.find("thead th").eq(parseInt(params.sort[0]));
                th_to_sort.stupidsort(params.dir[0]);
            }
            else {
                var th_to_sort = table.find("thead th").eq(0);
                th_to_sort.stupidsort();
            }
        }

        setup_sort(display_table);
        setup_sort(ignored_table);
    }

    /*
      Setup display hooks
    */
    $.asv.register_page('regressions', function(params) {
        $('#regressions-display').show()
        load_data(params);
    });
});
