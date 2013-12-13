$(function() {
    /* UTILITY FUNCTIONS */
    function arr_remove_from(a, x) {
        var out = [];
        $.each(a, function(i, val) {
            if (x !== val) {
                out.push(val);
            }
        });
        return out;
    };

    function obj_copy(obj) {
        newobj = {};
        $.each(obj, function(key, val) {
            newobj[key] = val;
        });
        return newobj;
    };

    function obj_length(obj) {
        var i = 0;
        for (x in obj)
            ++i;
        return i;
    };

    function obj_get_first_key(data) {
        for (var prop in data)
            return prop;
    };

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
        ['y', 'years', 60 * 60 * 24 * 7 * 52]
        ['C', 'centuries', 60 * 60 * 24 * 7 * 52 * 100]
    ];

    function pretty_second(x) {
        for (i = 0; i < time_units.length - 1; ++i) {
            if (x < time_units[i+1][2]) {
                return (x / time_units[i][2]).toFixed(3) + time_units[i][0];
            }
        }

        return 'inf';
    };

    function network_error(ajax, status, error) {
        $("#error-message").text(
            "Error fetching content. " +
            "Perhaps web server has gone down.");
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
    /* The index.json content as returned from the server */
    var master_json = {};
    /* A little div to handle tooltip placement on the graph */
    var tooltip = null;

    /* Fetch the master index.json and then set up the page elements
       based on it. */
    $.ajax({
        url: "index.json",
        cache: false
    }).done(function (index) {
        master_json = index;

        /* Page title */
        var project_name = $("#project-name")[0];
        project_name.textContent = index.project;
        project_name.setAttribute("href", index.project_url);
        $("#project-name").textContent = index.project;
        document.title = "airspeed velocity of an unladen " + index.project;

        var nav = $("#navigation");

        function make_panel(heading) {
            var panel = $('<div class="panel panel-default"/>');
            nav.append(panel);
            var panel_header = $(
                '<div class="panel-heading">' + heading + '</div>');
            panel.append(panel_header);
            var panel_body = $('<div class="panel-body"/>');
            panel.append(panel_body);
            return panel_body;
        }

        /* Machine selection */
        state['machine'] = index.params.machine;
        var panel_body = make_panel('machine');
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
                        state['machine'].push(machine);
                    } else {
                        state['machine'] = arr_remove_from(
                            state['machine'], machine);
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
                var panel_body = make_panel(param);
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

        /* Benchmark panel */
        var panel_body = make_panel('benchmark');
        var buttons = $(
            '<div class="btn-group-vertical" style="width: 100%" ' +
                'data-toggle="buttons"/>');
        panel_body.append(buttons);
        var i = 0;
        $.each(index.benchmarks, function(benchmark_name, benchmark) {
            var label = $('<label class="btn btn-default btn-xs"/>')
            buttons.append(label);
            var short_name = benchmark_name.split(".");
            short_name = short_name[short_name.length - 1];
            var input = $(
                '<input type="radio" name="options" id="option' + i + '">' +
                    short_name + '</input>');
            label.append(input);
            label.on('change', function(evt) {
                if (!evt.target.classList.contains("active")) {
                    current_benchmark = benchmark_name;
                    $("#title").text(benchmark_name);
                    replace_graphs();
                }
            });
            label.tooltip({
                title: benchmark.code,
                html: true,
                placement: 'right',
                container: 'body',
                animation: 'false'
            });
            if (i == 0) {
                label.button('toggle');
                current_benchmark = benchmark_name;
            }
            ++i;
        });


        $('#log-scale').on('click', function(evt) {
            log_scale = !evt.target.classList.contains("active");
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
                    var commit_hash = master_json.date_to_hash[item.datapoint[0]];
                    if (previous_hash !== commit_hash) {
                        previous_hash = commit_hash;
                        window.open(
                            master_json.show_commit_url + previous_hash,
                            '_blank');
                    }
                }
            }
        });
    }).fail(function () {
        network_error();
    });

    /* When the window resizes, redraw the graphs */
    $(window).resize(function() {
        update_graphs();
    });


    function replace_graphs() {

        /* Given the settings in the sidebar, generate a list of the
           graphs we need to load. */
        function collect_graphs(current_benchmark, state) {
            /* Given a specific group of parameters, generate the URL to
               use to load that graph. */
            function graph_to_path(benchmark_name, state) {
                var parts = [];
                $.each(state, function(key, value) {
                    if (value) {
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
                    'mem': null
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
                if (obj_length(matrix) == 0) {
                    return [{}];
                }

                var matrix = obj_copy(matrix);
                var key = obj_get_first_key(matrix);
                var entry = matrix[key];
                delete matrix[key];

                var results = []
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
                   list of all the graphs we need to load. */
                var graphs = permutations(state);
                /* Find where the parameters are different. */
                var different = find_different_properties(graphs);

                /* Generate a master list of URLs and legend labels for
                   the graphs. */
                var all = []
                $.each(graphs, function(i, graph) {
                    all.push([graph_to_path(current_benchmark, graph),
                              graph_label(graph, different)]);
                });
                return all;
            } else {
                return [];
            }
        };

        /* Before loading graphs, remove any that are currently
           active. */
        graphs = [];

        to_load = collect_graphs(current_benchmark, state);

        $.each(to_load, function(i, item) {
            $.ajax({
                url: item[0],
            }).done(function(data) {
                graphs.push({
                    data: data,
                    label: item[1]});
                update_graphs();
            }).fail(network_error);
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
                if (p !== null && p < min) {
                    min = p;
                }
                if (p > max) {
                    max = p;
                }
            }
        });

        if (log_scale) {
            min = Math.floor(Math.log(min) / Math.LN10);
            max = Math.ceil(Math.log(max) / Math.LN10);

            if (min == max) {
                --min;
            }

            var ticks = []
            for (var x = min; x <= max; ++x) {
                ticks.push(Math.pow(10, x));
            }

            options.yaxis.ticks = ticks;
            options.yaxis.transform = function(v) {
                return Math.log(v) / Math.LN10;
            };
            /* inverseTransform is required for plothover to work */
            options.yaxis.inverseTransform = function (v) {
                return Math.pow(10.0, v);
            }
            options.yaxis.tickDecimals = 3;
            options.yaxis.tickFormatter = function (v, axis) {
                return "10" + (
                    Math.round(
                        Math.log(v) / Math.LN10)).toString().sup();
            };
            options.yaxis.min = Math.pow(10, min);
            options.yaxis.max = Math.pow(10, max);
        } else if (master_json.benchmarks[current_benchmark].unit === 'seconds') {
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
                    return Math.floor(v / multiplier);
                };
            }
        }
    }

    /* Once we have all of the graphs loaded, send them to flot for
       drawing. */
    function update_graphs() {
        var colors = [
            '#73cf26', '#e89f0c', '#e0001a', '#2b16de', '#1fdeb0'
        ];

        var markings = [];
        $.each(master_json.tags, function(tag, date) {
            markings.push(
                { color: "#ddd", lineWidth: 1, xaxis: { from: date, to: date } }
            );
        });

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
                mode: "time",
                tickLength: 5,
                axisLabel: "commit date",
                axisLabelUseCanvas: true,
                axisLabelFontFamily: "sans-serif",
                axisLabelFontSizePixels: 12
            },
            yaxis: {
                axisLabel: master_json.benchmarks[current_benchmark].unit,
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

        var graph_div = $('#main-graph');
        var overview_div = $('#overview');

        var plot = $.plot(graph_div, graphs, options);

        /* Set up the "overview" plot */
        var overview = $.plot(overview_div, graphs, {
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
            overview.setSelection(ranges, true);
        });

        overview_div.unbind("plotselected");
        overview_div.bind("plotselected", function (event, ranges) {
            plot.setSelection(ranges);
            // Update things that depend on the range
            update_tags();
            update_range();
        });

        function update_range() {
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
    };
});
