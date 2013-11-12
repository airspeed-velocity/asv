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

    function pretty_second(x) {
        units = [
            ['ns', 0.000000001],
            ['μs', 0.000001],
            ['ms', 0.001],
            ['s', 1],
            ['m', 60],
            ['h', 60 * 60],
            ['d', 60 * 60 * 24],
            ['w', 60 * 60 * 24 * 7],
            ['y', 60 * 60 * 24 * 7 * 52]
            ['C', 60 * 60 * 24 * 7 * 52 * 100]
        ];

        for (i = 0; i < units.length; ++i) {
            if (x < units[i+1][1]) {
                return (x / units[i][1]).toFixed(3) + units[i][0];
            }
        }

        return 'int';
    };

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

            button.tooltip({'title': details,
                            'html': true,
                            'placement': 'right',
                            'container': 'body'});
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
        $.each(index.benchmark_names, function(i, benchmark_name) {
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
                    $("#title")[0].textContent = benchmark_name;
                    replace_graphs();
                }
            });
            if (i == 0) {
                label.button('toggle');
            }
        });

        current_benchmark = index.benchmark_names[0];

        $('#log-scale').on('click', function(evt) {
            log_scale = !evt.target.classList.contains("active");
            update_graphs();
        });
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
            });
        });
    }

    /* Handle log scaling the plot */
    function handle_log_scale(options) {
        if (log_scale && graphs.length) {
            /* Find the minimum and maximum values */
            var min = Infinity;
            var max = -Infinity;
            $.each(graphs, function(i, graph) {
                var data = graph.data;
                for (var j = 0; j < data.length; ++j) {
                    if (data[j][1] < min) {
                        min = data[j][1];
                    }
                    if (data[j][1] > max) {
                        max = data[j][1];
                    }
                }
            });

            min = Math.floor(Math.log(min) / Math.LN10);
            max = Math.ceil(Math.log(max) / Math.LN10);

            if (min == max) {
                --min;
            }

            var ticks = []
            for (var x = min; x <= max; ++x) {
                ticks.push(Math.pow(10, x));
            }

            options.yaxis = {
                ticks: ticks,
                transform:  function(v) {
                    return Math.log(v);
                },
                tickDecimals: 3,
                tickFormatter: function (v, axis) {
                    return "10" + (
                        Math.round(
                            Math.log(v) / Math.LN10)).toString().sup();
                },
                min: Math.pow(10, min),
                max: Math.pow(10, max)
            };
        }
    }

    /* Once we have all of the graphs loaded, send them to flot for
       drawing. */
    function update_graphs() {
        var options = {
	    series: {
	        lines: {
		    show: true,
		    lineWidth: 1,
	        },
                points: {
                    show: true
	        },
	        shadowSize: 0
	    },
            grid: {
	        hoverable: true,
                clickable: true
	    },
            xaxis: {
                mode: "time",
	        tickLength: 5
	    },
	    selection: {
	        mode: "x"
	    },
            legend: {
                position: "nw"
            }
        };

        handle_log_scale(options);

        var plot = $.plot("#main-graph", graphs, options);

        /* The tooltip on a point shows the exact timing and the
           commit hash */
        function showTooltip(x, y, contents) {
	    $("<div id='tooltip'>" + contents + "</div>").css({
		position: "absolute",
		display: "none",
		top: y + 5,
		left: x + 20,
		border: "1px solid #888",
		padding: "2px",
		"background-color": "#eee",
		opacity: 0.80
	    }).appendTo("body").fadeIn(200);
	}

        var previous_point = null;
        var previous_hash = null;
	$("#main-graph").bind("plothover", function (event, pos, item) {
	    if (item) {
		if (previous_point != item.datapoint) {
		    previous_point = item.datapoint;
		    $("#tooltip").remove();
		    var x = item.datapoint[0];
                    var y = item.datapoint[1];
                    var commit_hash = master_json.date_to_hash[x];
                    if (commit_hash) {
                        previous_hash = commit_hash;
		        showTooltip(
                            item.pageX, item.pageY,
                            pretty_second(y) + " @ " + commit_hash.substring(0, 8));
                    }
		}
	    } else {
		$("#tooltip").remove();
		previous_point = null;
                previous_hash = null;
	    }
	});

        /* Clicking on a point should display the particular commit
           hash in another tab. */
        $("#main-graph").bind("plotclick", function (event, pos, item) {
            if (previous_hash) {
                window.open(master_json.show_commit_url + previous_hash, '_blank');
            }
	});

        /* Set up the "overview" plot */
        var overview = $.plot("#overview", graphs, {
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

	$("#main-graph").bind("plotselected", function (event, ranges) {
	    // do the zooming

	    plot = $.plot("#main-graph", graphs, $.extend(true, {}, options, {
		xaxis: {
		    min: ranges.xaxis.from,
		    max: ranges.xaxis.to
		}
	    }));

	    // don't fire event on the overview to prevent eternal loop
	    overview.setSelection(ranges, true);
	});

	$("#overview").bind("plotselected", function (event, ranges) {
	    plot.setSelection(ranges);
	});
    };
});
