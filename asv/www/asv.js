$(function() {
    var colors = [
        '#247AAD',
        '#E24A33',
        '#988ED5',
        '#777777',
        '#FBC15E',
        '#8EBA42',
        '#FFB5B8'
    ];

    /* UTILITY FUNCTIONS */
    function arr_remove_from(a, x) {
        var out = [];
        $.each(a, function(i, val) {
            if (x !== val) {
                out.push(val);
            }
        });
        return out;
    }

    function obj_copy(obj) {
        newobj = {};
        $.each(obj, function(key, val) {
            newobj[key] = val;
        });
        return newobj;
    }

    function obj_length(obj) {
        var i = 0;
        for (var x in obj)
            ++i;
        return i;
    }

    function obj_get_first_key(data) {
        for (var prop in data)
            return prop;
    }

    /* Callback a function when an element comes in view */
    function callback_in_view(element, func) {
        function handler(evt) {
            var visible = (
                (element.offset().top <= $(window).height() + $(window).scrollTop()) &&
                    (element.offset().top + element.height() >= $(window).scrollTop()));
            if (visible) {
                func();
                $(window).unbind('scroll', handler);
            }
        }
        $(window).on('scroll', handler);
        $(window).scroll();
    }

    time_units = [
        ['ps', 'picoseconds', 0.000000000001],
        ['ns', 'nanoseconds', 0.000000001],
        ['μs', 'microseconds', 0.000001],
        ['ms', 'milliseconds', 0.001],
        ['s', 'seconds', 1],
        ['m', 'minutes', 60],
        ['h', 'hours', 60 * 60],
        ['d', 'days', 60 * 60 * 24],
        ['w', 'weeks', 60 * 60 * 24 * 7],
        ['y', 'years', 60 * 60 * 24 * 7 * 52],
        ['C', 'centuries', 60 * 60 * 24 * 7 * 52 * 100]
    ];

    function pretty_second(x) {
        for (i = 0; i < time_units.length - 1; ++i) {
            if (x < time_units[i+1][2]) {
                return (x / time_units[i][2]).toFixed(3) + time_units[i][0];
            }
        }

        return 'inf';
    }

    function network_error(ajax, status, error) {
        $("#error-message").text(
            "Error fetching content. " +
            "Perhaps web server has gone down.");
        $("#error").modal('show');
    }

    function no_data(ajax, status, error) {
        $("#error-message").text(
            "No data for this combination of filters. ");
        $("#error").modal('show');
    }

    /* GLOBAL STATE */
    /* The state of the parameters in the sidebar.  Dictionary mapping
       strings to arrays containing the "enabled" configurations. */
    var state = {};
    /* The name of the current benchmark being displayed. */
    var current_benchmark = null;
    /* An array of graphs being displayed. */
    var graphs = [];
    /* True when log scaling is enabled. */
    var log_scale = false;
    /* True when zooming in on the y-axis. */
    var zoom_y_axis = false;
    /* True when log scaling is enabled. */
    var reference_scale = false;
    /* True when selecting a reference point */
    var select_reference = false;
    /* The reference value */
    var reference = 1.0;
    /* Is even commit spacing being used? */
    var even_spacing = false;
    var even_dates = {};
    var even_dates_inv = {};
    /* The index.json content as returned from the server */
    var master_json = {};
    /* A little div to handle tooltip placement on the graph */
    var tooltip = null;
    /* X-axis coordinate axis in the data set; always 0 for
       non-parameterized tests where time is the only potential x-axis */
    var x_coordinate_axis = 0;
    var x_coordinate_is_category = false;
    /* List of lists of value combinations to plot (apart from x-axis)
       in parameterized tests. */
    var benchmark_param_selection = [[null]];

    function display_benchmark(bm_name) {
        $('#graph-display').show();
        $('#summary-display').hide();
        $('.tooltip').remove();

        if (reference_scale) {
            reference_scale = false;
            $('#reference').removeClass('active');
            reference = 1.0;
        }
        current_benchmark = bm_name;
        $("#title").text(bm_name);
        setup_benchmark_params();
        replace_graphs();
    }

    function make_panel(nav, heading) {
        var panel = $('<div class="panel panel-default"/>');
        nav.append(panel);
        var panel_header = $(
            '<div class="panel-heading">' + heading + '</div>');
        panel.append(panel_header);
        var panel_body = $('<div class="panel-body"/>');
        panel.append(panel_body);
        return panel_body;
    }

    /* Fetch the master index.json and then set up the page elements
       based on it. */
    $.ajax({
        url: "index.json",
        cache: false
    }).done(function (index) {
        master_json = index;

        var nav = $("#navigation");

        /* Page title */
        var project_name = $("#project-name")[0];
        project_name.textContent = index.project;
        project_name.setAttribute("href", index.project_url);
        $("#project-name").textContent = index.project;
        document.title = "airspeed velocity of an unladen " + index.project;

        /* Machine selection */
        state.machine = index.params.machine;
        var panel_body = make_panel(nav, 'machine');
        var buttons = $(
            '<div class="btn-group-vertical" style="width: 100%" ' +
                'data-toggle="buttons"/>');
        panel_body.append(buttons);
        $.each(index.params.machine, function(i, machine) {
            var button = $(
                '<a class="btn btn-default btn-xs active" role="button">' +
                    machine + '</a>');
            buttons.append(button);

            if (index.params.machine.length > 1) {
                button.on('click', function(evt) {
                    if (!evt.target.classList.contains("active")) {
                        state.machine.push(machine);
                    } else {
                        state.machine = arr_remove_from(
                            state.machine, machine);
                    }
                    replace_graphs();
                });
            }

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
            state[param] = values;

            if (values.length > 1 && param !== 'machine') {
                var panel_body = make_panel(nav, param);
                var buttons = $(
                    '<div class="btn-group btn-group-justified" ' +
                        'data-toggle="buttons"/>');
                panel_body.append(buttons);
                $.each(values, function(i, value) {
                    var value_display;
                    if (!value)
                        value_display = '[none]';
                    else
                        value_display = value;

                    var button = $(
                        '<a class="btn btn-default btn-xs active" role="button">' +
                            value_display + '</a>');
                    buttons.append(button);

                    if (values.length > 1) {
                        button.on('click', function(evt) {
                            if (!evt.target.classList.contains("active")) {
                                state[param].push(value);
                            } else {
                                state[param] = arr_remove_from(
                                    state[param], value);
                            }
                            replace_graphs();
                        });
                    }
                });
            }
        });

        /* Add insertion point for benchmark parameters */
        bench_params_nav = $("<div id='navigation-params'/>");
        nav.append(bench_params_nav);

        /* Benchmark panel */
        panel_body = make_panel(nav, 'benchmark');

        var tree = $('<ul class="nav nav-list" style="padding-left: 0px"/>');
        panel_body.append(tree);
        var cursor = [];
        var stack = [tree];

        /* Note: this relies on the fact that the benchmark names are
           sorted. */
        $.each(index.benchmarks, function(bm_name, bm) {
            var parts = bm_name.split('.');
            var i = 0;
            var j;

            for (; i < cursor.length; ++i) {
                if (cursor[i] !== parts[i]) {
                    break;
                }
            }

            for (j = cursor.length - 1; j >= i; --j) {
                stack.pop();
                cursor.pop();
            }

            for (j = i; j < parts.length - 1; ++j) {
                var top = $(
                    '<li class="dropdown">' +
                        '<label class="nav-header"><b class="caret"/> ' + parts[j] +
                        '</label><ul class="nav nav-list tree"/></li>');
                stack[stack.length - 1].append(top);
                stack.push($(top.children()[1]));
                cursor.push(parts[j]);
                top.children('ul.tree').toggle(0);

                $(top.children()[0]).click(function () {
                    $(this).parent().children('ul.tree').toggle(150);
                });
            }

            var top = $('<li><a href="#' + bm_name + '">' + parts[parts.length - 1] + '</li>');
            stack[stack.length - 1].append(top);

            top.tooltip({
                title: bm.code,
                html: true,
                placement: 'right',
                container: 'body',
                animation: 'false'
            });
        });

        make_summary();

        $('#log-scale').on('click', function(evt) {
            log_scale = !evt.target.classList.contains("active");
            reference_scale = false;
            zoom_y_axis = false;
            $('#reference').removeClass('active');
            $('#zoom-y-axis').removeClass('active');
            reference = 1.0;
            update_graphs();
        });

        $('#zoom-y-axis').on('click', function(evt) {
            zoom_y_axis = !evt.target.classList.contains("active");
            reference_scale = false;
            log_scale = false;
            $('#reference').removeClass('active');
            $('#log-scale').removeClass('active');
            reference = 1.0;
            update_graphs();
        });

        $('#reference').on('click', function(evt) {
            reference_scale = !evt.target.classList.contains("active");
            log_scale = false;
            zoom_y_axis = false;
            $('#log-scale').removeClass('active');
            $('#zoom-y-axis').removeClass('active');
            if (!reference_scale) {
                update_graphs();
            } else {
                $('#reference').popover({
                    content: 'Select a reference point',
                    placement: 'top',
                    container: 'body'});
                $('#reference').popover('show');
                reference = 1.0;
                select_reference = true;
            }
        });

        $('#even-spacing').on('click', function(evt) {
            even_spacing = !evt.target.classList.contains("active");
            update_graphs();
        });

        tooltip = $("<div></div>");
        tooltip.appendTo("body");

        /* The tooltip on a point shows the exact timing and the
           commit hash */
        function showTooltip(x, y, contents) {
            tooltip
                .css({
                    position: "absolute",
                    display: "none",
                    top: y - 4,
                    left: x - 2,
                    width: 4,
                    height: 4
                })
                .fadeIn(0)
                .tooltip({
                    title: contents,
                    html: true,
                    placement: 'top',
                    container: 'body',
                    animation: false
                })
                .tooltip('show');
        }

        var previous_hover = null;
        $("#main-graph").bind("plothover", function (event, pos, item) {
            if (item) {
                if (previous_hover != item.datapoint) {
                    previous_hover = item.datapoint;
                    var y = item.datapoint[1];
                    var commit_hash = master_json.date_to_hash[item.datapoint[0]];
                    if (commit_hash) {
                        showTooltip(
                            item.pageX, item.pageY,
                            pretty_second(y) + " @ " + commit_hash);
                    }
                }
            } else {
                tooltip.tooltip("destroy");
                previous_point = null;
            }
        });

        /* Clicking on a point should display the particular commit
           hash in another tab. */
        var previous_click;
        var previous_hash;
        $("#main-graph").bind("plotclick", function (event, pos, item) {
            if (item) {
                if (previous_click != item.datapoint) {
                    previous_click = item.datapoint;
                    if (select_reference) {
                        $('#reference').popover('destroy');
                        select_reference = false;
                        reference = item.datapoint[1];
                        update_graphs();
                    } else {
                        var commit_hash = master_json.date_to_hash[item.datapoint[0]];
                        if (previous_hash !== commit_hash) {
                            previous_hash = commit_hash;
                            window.open(
                                master_json.show_commit_url + previous_hash,
                                '_blank');
                        }
                    }
                }
            }
        });

        function hashchange() {
            var hash = window.location.hash.replace('#', '');

            if (hash === '') {
                show_summary();
            } else {
                display_benchmark(hash);
            }
        }

        $(window).on('hashchange', hashchange);

        hashchange();
    }).fail(function () {
        network_error();
    });

    /* When the window resizes, redraw the graphs */
    $(window).resize(function() {
        update_graphs();
    });

    function make_summary() {
        $.each(master_json.benchmarks, function(bm_name, bm) {
            var container = $(
                '<a class="btn" href="#' + bm_name +
                '" style="float: left; width: 300px; height: 116px; padding: 4px"/>');
            var plot_div = $(
                '<div id="summary-' + bm_name + '" style="width: 292px; height: 92px"/>');
            var name = $('<div style="width: 292px; overflow: hidden">' + bm_name + '</div>');
            name.tooltip({
                title: bm_name,
                html: true,
                placement: 'top',
                container: 'body',
                animation: false
            });

            plot_div.tooltip({
                title: bm.code,
                html: true,
                placement: 'bottom',
                container: 'body',
                animation: false
            });

            container.append(name);
            container.append(plot_div);
            $('#summary-display').append(container);

            callback_in_view(plot_div, function() {
                $.ajax({
                    url: 'graphs/summary/' + bm_name + '.json',
                    cache: false
                }).done(function(data) {
                    var options = {
                        colors: colors,
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
                            minBorderMargin: 0
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

                    var plot = $.plot(
                        plot_div, [{data: data}], options);
                }).fail(function() {
                    // TODO: Handle failure
                });
            });
        });
    }

    function show_summary() {
        $('#graph-display').hide();
        $('#summary-display').show();
        $("#title").text("All benchmarks");
        $('.tooltip').remove();
    }

    function setup_benchmark_params() {
        if (!current_benchmark) {
            x_coordinate_axis = 0;
            x_coordinate_is_category = false;
            benchmark_param_selection = [[null]];
            return
        }

        var params = master_json.benchmarks[current_benchmark].params;
        var param_names = master_json.benchmarks[current_benchmark].param_names;

        /* Default plot: time series */
        x_coordinate_axis = 0;

        /* Default plot: up to 4 different parameter values */
        benchmark_param_selection = [[null]];
        if (params.length >= 1) {
            var item = [];
            for (var j = 0; j < params[0].length && j < 4; ++j) {
                item.push(j);
            }
            benchmark_param_selection.push(item);
            for (var k = 1; k < params.length; ++k) {
                benchmark_param_selection.push([0]);
            }
        }

        check_x_coordinate_axis();
        replace_benchmark_params_ui();
    }

    function replace_benchmark_params_ui() {
        var params = master_json.benchmarks[current_benchmark].params;
        var param_names = master_json.benchmarks[current_benchmark].param_names;

        /* Parameter selection UI */
        var nav = $('#navigation-params');
        nav.empty();

        if (params.length == 0) {
            /* Simple time series: no need for parameter selection UI */
            return;
        }

        /* x-axis selector */
        {
            var panel_body = make_panel(nav, "x-axis");
            var buttons = $(
                '<div class="btn-group btn-group-justified" ' +
                    'data-toggle="buttons"/>');
            panel_body.append(buttons);

            function add_button(axis) {
                if (axis == 0) {
                    text = "commit";
                } else {
                    text = param_names[axis - 1];
                }
                var button = $(
                    '<a class="btn btn-default btn-xs" role="button"/>');
                if (x_coordinate_axis == axis) {
                    button.addClass('active');
                }
                button.text(text);

                button.on('click', function (evt) {
                    buttons.children().removeClass('active');
                    x_coordinate_axis = axis;

                    /* Reset parameter selection for this axis to
                       avoid inadvertently showing many graphs when
                       changing axes later on */
                    if (axis == 0) {
                        benchmark_param_selection[axis] = [null];
                    } else {
                        benchmark_param_selection[axis] = [0];
                    }

                    check_x_coordinate_axis();
                    replace_benchmark_params_ui();
                    replace_graphs();
                    update_graphs();
                });

                buttons.append(button);
            }

            for (var axis = 0; axis < params.length + 1; ++axis) {
                add_button(axis);
            }
        }

        /* Time/commit value selector */
        if (x_coordinate_axis != 0) {
            var panel_body = make_panel(nav, "commit");

            var buttons = $(
                '<div class="btn-group btn-group-vertical" ' +
                    'data-toggle="buttons" style="width: 100%; max-height: 20ex; overflow-y: scroll;" />');
            panel_body.append(buttons);

            /* Generate list of all commits+dates */
            var dates = Object.keys(master_json.date_to_hash).map(function (x) { return parseInt(x); });
            dates.sort();
            dates.push(null);
            dates.reverse();

            $.each(dates, function(idx, date) {
                var button = $(
                    '<a class="btn btn-default btn-xs" role="button" />');
                if (date === null) {
                    button.text("last");
                } else {
                    var date_fmt = new Date(date);
                    button.text(master_json.date_to_hash[date]
                                + " "
                                + date_fmt.toUTCString());
                }
                buttons.append(button);

                if ($.inArray(date, benchmark_param_selection[0]) != -1) {
                    button.addClass('active');
                }

                button.on('click', function(evt) {
                    var idx = $.inArray(date, benchmark_param_selection[0]);
                    if (!evt.target.classList.contains("active")) {
                        if (idx == -1) {
                            benchmark_param_selection[0].push(date);
                            benchmark_param_selection[0].sort();
                        }
                    } else {
                        if (idx != -1) {
                            benchmark_param_selection[0].splice(idx, 1);
                        }
                    }
                    replace_graphs();
                    update_graphs();
                });
            });
        }

        /* Parameters axes value selector */
        $.each(params, function(param_idx, values) {
            var axis = param_idx + 1;

            if (axis == x_coordinate_axis) {
                return;
            }

            name = param_names[param_idx];

            var panel_body = make_panel(nav, name);

            var buttons = $(
                '<div class="btn-group btn-group-justified" ' +
                    'data-toggle="buttons"/>');
            panel_body.append(buttons);

            /* Add benchmark parameters */
            $.each(values, function(value_idx, value) {
                var value_display;
                value_display = '' + value;

                var button = $(
                    '<a class="btn btn-default btn-xs active" role="button"/>');
                button.text(value_display);
                if ($.inArray(value_idx, benchmark_param_selection[axis]) == -1) {
                    button.removeClass('active');
                }

                buttons.append(button);

                button.on('click', function(evt) {
                    var new_selection = [];
                    var old_selection = benchmark_param_selection[param_idx+1];

                    if (!evt.target.classList.contains("active")) {
                        for (var k = 0; k < params[param_idx].length; ++k) {
                            if ($.inArray(k, old_selection) != -1 || k == value_idx) {
                                new_selection.push(k);
                            }
                        }
                    } else {
                        for (var k = 0; k < params[param_idx].length; ++k) {
                            if ($.inArray(k, old_selection) != -1 && k != value_idx) {
                                new_selection.push(k);
                            }
                        }
                    }
                    benchmark_param_selection[param_idx+1] = new_selection;
                    replace_graphs();
                    update_graphs();
                });
            });
        });
    }

    /* Check if x-axis is a category axis */
    function check_x_coordinate_axis() {
        if (!current_benchmark) {
            return;
        }

        var params = master_json.benchmarks[current_benchmark].params;
        x_coordinate_is_category = false;
        if (x_coordinate_axis != 0) {
            for (var j = 0; j < params[x_coordinate_axis-1].length; ++j) {
                if (typeof params[x_coordinate_axis-1][j] != "number") {
                    x_coordinate_is_category = true;
                    break;
                }
            }
        }
    }

    function replace_graphs() {
        /* Given the settings in the sidebar, generate a list of the
           graphs we need to load. */
        function collect_graphs(current_benchmark, state, param_selection) {
            /* Given a specific group of parameters, generate the URL to
               use to load that graph. */
            function graph_to_path(benchmark_name, state) {
                var parts = [];
                $.each(state, function(key, value) {
                    if (value !== null) {
                        parts.push(key + "-" + value);
                    } else {
                        parts.push(key);
                    }
                });
                parts.sort();
                parts.splice(0, 0, "graphs");
                parts.push(benchmark_name);
                return parts.join('/') + ".json";
            }

            /* Given a specific group of parameters, generate the legend
               label to display for that line. Differences is an object of
               parameters that have different values across all graphs. */
            function graph_label(state, differences) {
                ignore = {
                    'os': null,
                    'cpu': null,
                    'arch': null,
                    'ram': null
                };

                var parts = [];
                $.each(state, function(key, value) {
                    if (!ignore.hasOwnProperty(key) &&
                        differences.hasOwnProperty(key)) {
                        if (value) {
                            parts.push(key + "-" + value);
                        } else {
                            parts.push(key);
                        }
                    }
                });
                parts.sort();
                return parts.join('; ');
            }

            /* For a given parameter matrix, generate all permutations. */
            function permutations(matrix) {
                if (obj_length(matrix) === 0) {
                    return [{}];
                }

                matrix = obj_copy(matrix);
                var key = obj_get_first_key(matrix);
                var entry = matrix[key];
                delete matrix[key];

                var results = [];
                $.each(permutations(matrix), function(i, result) {
                    result = obj_copy(result);
                    if (entry.length) {
                        $.each(entry, function(i, value) {
                            result[key] = value;
                            results.push(obj_copy(result));
                        });
                    } else {
                        result[key] = null;
                        results.push(obj_copy(result));
                    }
                });

                results.sort();
                return results;
            }

            /* For all of the selected graphs, find out which parameters
               have different values across them.  We don't want to show
               parameters that are the same across all graphs in the
               legend labels, as that information is not really
               necessary. */
            function find_different_properties(graphs) {
                var different = {};
                var last_values = obj_copy(graphs[0]);
                $.each(graphs, function(i, graph) {
                    $.each(graph, function(key, val) {
                        if (last_values[key] != val) {
                            different[key] = true;
                        }
                    });
                });
                return different;
            }

            if (current_benchmark) {
                /* For the current set of enabled parameters, generate a
                   list of all the permutations we need to load. */
                var state_permutations = permutations(state);
                /* Find where the parameters are different. */
                var different = find_different_properties(state_permutations);
                /* For parameterized tests: names of benchmark parameters */
                var params = master_json.benchmarks[current_benchmark].params;
                var param_names = master_json.benchmarks[current_benchmark].param_names;
                /* Selected permutations of benchmark parameters */
                var param_permutations = permutations(param_selection);

                /* Generate a master list of URLs and legend labels for
                   the graphs. */
                var all = [];
                $.each(state_permutations, function(i, perm) {
                    var graph_contents = [];
                    $.each(param_permutations, function(k, param_perm) {
                        /* For each state value, there can be several
                           benchmark parameter sets to plot */
                        labels = obj_copy(perm);
                        for (var axis = 0; axis < params.length + 1; ++axis) {
                            if (axis != x_coordinate_axis) {
                                if (axis == 0) {
                                    /* Add time/commit value to the labels */
                                    var timestamp = param_perm[axis];
                                    different["commit"] = true;
                                    if (timestamp === null) {
                                        labels["commit"] = "last";
                                    }
                                    else {
                                        labels["commit"] = ""+master_json.date_to_hash[timestamp];
                                    }
                                }
                                else if (params[axis-1].length > 1) {
                                    /* Add parameter value to the labels */
                                    if (param_perm[axis] === null) {
                                        /* Empty permutation */
                                        return;
                                    }
                                    different[param_names[axis-1]] = true;
                                    labels[param_names[axis-1]] = "" + params[axis-1][param_perm[axis]];
                                }
                            }
                        }
                        graph_contents.push([param_perm,
                                             graph_label(labels, different)]);
                    });
                    all.push([graph_to_path(current_benchmark, perm),
                              graph_contents]);
                });
                return all;
            } else {
                return [];
            }
        }

        /* Convert loaded graph data to a format flot understands, by
           treating either time or one of the parameters as x-axis,
           and selecting only one value of the remaining axes */
        function filter_graph_data(raw_series, x_axis, other_indices) {
            var params = master_json.benchmarks[current_benchmark].params;

            if (params.length == 0) {
                /* Simple time series */
                return raw_series;
            }

            /* Compute position of data entry in the results list,
               and stride corresponding to plot x-axis parameter */
            var stride = 1;
            var param_stride = 0;
            var param_idx = 0;
            for (var k = params.length - 1; k >= 0; --k) {
                if (k == x_axis - 1) {
                    param_stride = stride;
                }
                else {
                    param_idx += other_indices[k + 1] * stride;
                }
                stride *= params[k].length;
            }

            if (x_axis == 0) {
                /* x-axis is time axis */
                var series = new Array(raw_series.length);
                for (var k = 0; k < raw_series.length; ++k) {
                    if (raw_series[k][1] === null) {
                        series[k] = [raw_series[k][0], null];
                    } else {
                        series[k] = [raw_series[k][0],
                                     raw_series[k][1][param_idx]];
                    }
                }
                return series;
            }
            else {
                /* x-axis is some parameter axis */
                var time_idx = null;
                if (other_indices[0] === null) {
                    time_idx = raw_series.length - 1;
                }
                else {
                    /* Need to search for the correct time value */
                    for (var k = 0; k < raw_series.length; ++k) {
                        if (raw_series[k][0] == other_indices[0]) {
                            time_idx = k;
                            break;
                        }
                    }
                    if (time_idx === null) {
                        /* No data points */
                        return [];
                    }
                }

                var x_values = params[x_axis - 1];
                var series = new Array(x_values.length);
                for (var k = 0; k < x_values.length; ++k) {
                    if (raw_series[time_idx][1] === null) {
                        series[k] = [x_values[k], null];
                    }
                    else {
                        series[k] = [x_values[k],
                                     raw_series[time_idx][1][param_idx]];
                    }
                    param_idx += param_stride;
                }
                return series;
            }
        }

        /* Before loading graphs, remove any that are currently
           active. */
        graphs = [];

        to_load = collect_graphs(current_benchmark, state, benchmark_param_selection);
        var failures = 0;
        var count = 1;

        $.each(to_load, function(i, item) {
            $.ajax({
                url: item[0],
                cache: false
            }).done(function(data) {
                $.each(item[1], function(j, graph_content) {
                    var series;
                    series = filter_graph_data(data,
                                               x_coordinate_axis,
                                               graph_content[0]);
                    graphs.push({
                        data: series,
                        label: graph_content[1],
                        bars: { order: count, },
                    });
                    count += 1;
                });
                update_graphs();
            }).fail(function() {
                failures += 1;
                if (failures == to_load.length) {
                    /* If we don't get any results, we check that the
                    webserver is still live by loading a file we know
                    we have.  If that fails, too, then the webserver
                    is probably down. */
                    $.ajax({
                        url: "swallow.ico",
                        cache: false
                    }).done(function (index) {
                        update_graphs();
                        no_data();
                    }).fail(function () {
                        network_error();
                    });
                }
            });
        });
    }

    /* Handle log scaling the plot */
    function handle_y_scale(options) {
        if (!graphs.length)
            return;

        /* Find the minimum and maximum values */
        var min = Infinity;
        var max = -Infinity;
        $.each(graphs, function(i, graph) {
            var data = graph.data;
            for (var j = 0; j < data.length; ++j) {
                var p = data[j][1];
                if (p !== null) {
                    if (p < min) {
                        min = p;
                    }
                    if (p > max) {
                        max = p;
                    }
                }
            }
        });

        min /= reference;
        max /= reference;

        if (log_scale || reference_scale) {
            min = Math.floor(Math.log(min) / Math.LN10);
            max = Math.ceil(Math.log(max) / Math.LN10);

            if (min == max) {
                --min;
            }

            var ticks = [];
            for (var x = min; x <= max; ++x) {
                ticks.push(Math.pow(10, x) * reference);
            }

            options.yaxis.ticks = ticks;
            options.yaxis.transform = function(v) {
                return Math.log(v / reference) / Math.LN10;
            };
            /* inverseTransform is required for plothover to work */
            options.yaxis.inverseTransform = function (v) {
                return Math.pow(10.0, v);
            };
            options.yaxis.tickDecimals = 3;
            options.yaxis.tickFormatter = function (v, axis) {
                return "10" + (
                    Math.round(
                        Math.log(v / reference) / Math.LN10)).toString().sup();
            };
            options.yaxis.min = Math.pow(10, min) * reference;
            options.yaxis.max = Math.pow(10, max) * reference;

        } else if (master_json.benchmarks[current_benchmark].unit === 'seconds') {

            if (!zoom_y_axis) {
                options.yaxis.min = 0.0;
                options.yaxis.max = max * 1.3;
            }

            var unit_name = null;
            var multiplier = null;
            for (var i = 0; i < time_units.length - 1; ++i) {
                if (min < time_units[i+1][2]) {
                    unit_name = time_units[i][1];
                    multiplier = time_units[i][2];
                    break;
                }
            }

            if (unit_name) {
                options.yaxis.axisLabel = unit_name;
                options.yaxis.tickFormatter = function (v, axis) {
                    return (v / multiplier).toPrecision(3);
                };
            }
        }
    }

    function handle_x_scale(options) {
        if (!graphs.length)
            return;

        if (x_coordinate_axis == 0) {
            if (even_spacing) {
                var all_dates = {};
                $.each(graphs, function(i, graph) {
                    var data = graph.data;
                    for (var j = 0; j < data.length; ++j) {
                        all_dates[data[j][0]] = null;
                    }
                });
                all_dates = Object.keys(all_dates);
                all_dates.sort();

                even_dates = {};
                even_dates_inv = {};
                var last_date = null;
                var j = 0;
                for (var i = 0; i < all_dates.length; ++i) {
                    if (all_dates[i] != last_date) {
                        even_dates[all_dates[i]] = j;
                        even_dates_inv[j] = all_dates[i];
                        ++j;
                        last_date = all_dates[i];
                    }
                }

                options.xaxis.axisLabel = 'commits';
                options.xaxis.transform = function(v) {
                    return even_dates[v];
                };
                /* inverseTransform is required for plothover to work */
                options.xaxis.inverseTransform = function (v) {
                    return even_dates_inv[v];
                };
                options.xaxis.tickFormatter = function (v, axis) {
                    return "";
                };
            } else {
                options.xaxis.mode = 'time';
                options.xaxis.axisLabel = 'commit date';
            }
        } else {
            if (x_coordinate_is_category) {
                options.xaxis.mode = 'categories';
                options.xaxis.tickLength = 0;
                options.series = {
                    bars: {
                        show: true,
                        barWidth: 0.6 / graphs.length,
                        align: "center"
                    },
                    points: {
                        show: true
                    }
                };
            }
            var param_names = master_json.benchmarks[current_benchmark].param_names;
            options.xaxis.axisLabel = param_names[x_coordinate_axis-1];
        }
    }

    /* Once we have all of the graphs loaded, send them to flot for
       drawing. */
    function update_graphs() {
        if (current_benchmark === null) {
            return;
        }

        var markings = [];
        $.each(master_json.tags, function(tag, date) {
            markings.push(
                { color: "#ddd", lineWidth: 1, xaxis: { from: date, to: date } }
            );
        });

        var unit;
        if (reference_scale) {
            unit = 'relative';
        } else {
            unit = master_json.benchmarks[current_benchmark].unit;
        }

        var options = {
            colors: colors,
            series: {
                lines: {
                    show: true,
                    lineWidth: 1
                },
                points: {
                    show: true
                },
                shadowSize: 0
            },
            grid: {
                hoverable: true,
                clickable: true,
                markings: markings
            },
            xaxis: {
                tickLength: 5,
                axisLabel: "",
                axisLabelUseCanvas: true,
                axisLabelFontFamily: "sans-serif",
                axisLabelFontSizePixels: 12
            },
            yaxis: {
                axisLabel: "",
                axisLabelUseCanvas: true,
                axisLabelFontFamily: "sans-serif",
                axisLabelFontSizePixels: 12
            },
            selection: {
                mode: "x"
            },
            legend: {
                position: "nw"
            }
        };

        handle_y_scale(options);
        handle_x_scale(options);

        var graph_div = $('#main-graph');
        var overview_div = $('#overview');

        var plot = $.plot(graph_div, graphs, options);

        /* Set up the "overview" plot */
        var overview = null;

        if (x_coordinate_axis != 0) {
            /* Overview is useful mostly for the time axis */
            overview_div.empty();
        }  else {
            overview = $.plot(overview_div, graphs, {
                colors: colors,
                series: {
                    lines: {
                        show: true,
                        lineWidth: 1
                    },
                    shadowSize: 0
                },
                xaxis: {
                    ticks: [],
                    mode: "time"
                },
                yaxis: {
                    ticks: [],
                    min: 0,
                    autoscaleMargin: 0.1
                },
                selection: {
                    mode: "x"
                },
                legend: {
                    show: false
                }
            });
        }

        graph_div.unbind("plotselected");
        graph_div.bind("plotselected", function (event, ranges) {
            // do the zooming
            plot = $.plot(graph_div, graphs, $.extend(true, {}, options, {
                xaxis: {
                    min: ranges.xaxis.from,
                    max: ranges.xaxis.to
                }
            }));

            // Update things that depend on the range
            update_tags();
            update_range();

            // don't fire event on the overview to prevent eternal loop
            if (overview) {
                overview.setSelection(ranges, true);
            }
        });

        overview_div.unbind("plotselected");
        overview_div.bind("plotselected", function (event, ranges) {
            plot.setSelection(ranges);
            // Update things that depend on the range
            update_tags();
            update_range();
        });

        function update_range() {
            if (x_coordinate_axis != 0) {
                /* Only applies when x-axis is the time axis */
                return;
            }

            /* Find the minimum and maximum values */
            var min = Infinity;
            var left = plot.getAxes().xaxis.min;
            $.each(graphs, function(i, graph) {
                var data = graph.data;
                for (var j = 0; j < data.length; ++j) {
                    var p = data[j][0];
                    if (p !== null && p >= left) {
                        if (p < min) {
                            min = p;
                        }
                        break;
                    }
                }
            });

            var max = -Infinity;
            var right = plot.getAxes().xaxis.max;
            $.each(graphs, function(i, graph) {
                var data = graph.data;
                for (var j = data.length - 1; j >= 0; --j) {
                    var p = data[j][0];
                    if (p !== null && p <= right) {
                        if (p > max) {
                            max = p;
                        }
                        break;
                    }
                }
            });

            var result;
            if (min === null || max === null || min > max) {
                result = '';
            } else if (min == max) {
                result = master_json.date_to_hash[min] + '^!';
            } else {
                var first_commit = master_json.date_to_hash[min];
                var last_commit = master_json.date_to_hash[max];
                result = first_commit + ".." + last_commit;
            }
            $("#range")[0].value = result;
        }

        function update_tags() {
            /* Add the tags as vertical grid lines */
            var canvas = plot.getCanvas();
            var xmin = plot.getAxes().xaxis.min;
            var xmax = plot.getAxes().xaxis.max;
            $.each(master_json.tags, function(tag, date) {
                if (date >= xmin && date <= xmax) {
                    var p = plot.pointOffset({x: date, y: 0});
                    var o = plot.getPlotOffset();

                    graph_div.append(
                        "<div style='position:absolute;" +
                            "left:" + p.left + "px;" +
                            "bottom:" + (canvas.height - o.top) + "px;" +
                            "color:#666;font-size:smaller'>" + tag + "</div>");
                }
            });
        }

        update_tags();
        update_range();
    }

    show_summary();
});
