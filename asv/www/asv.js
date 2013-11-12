$(function() {
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

    function get_first_key(data) {
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

    var state = {};
    var current_test = null;
    var graphs = [];
    var date_to_hash = {};
    var show_commit_url = null;

    function setup(index) {
        var project_name = $("#project-name")[0];
        project_name.textContent = index.package;
        project_name.setAttribute("href", index.project_url);
        $("#project-name").textContent = index.package;

        document.title = "airspeed velocity of an unladen " + index.package;

        var nav = $("#navigation");

        state['machine'] = index.params.machine;
        var panel = $('<div class="panel panel-default"/>');
        nav.append(panel);
        var panel_header = $('<div class="panel-heading">machine</div>');
        panel.append(panel_header);
        var panel_body = $('<div class="panel-body"/>');
        panel.append(panel_body);
        var buttons = $('<div class="btn-group-vertical" style="width: 100%" data-toggle="buttons"/>');
        panel_body.append(buttons);
        $.each(index.params.machine, function(i, machine) {
            var button = $('<a class="btn btn-default btn-xs active" role="button">' + machine + '</a>');
            buttons.append(button);

            if (index.params.machine.length > 1) {
                button.on('click', function(evt) {
                    if (!evt.target.classList.contains("active")) {
                        state['machine'].push(machine);
                    } else {
                        state['machine'] = arr_remove_from(state['machine'], machine);
                    }
                    replace_graphs();
                });
            }

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

        $.each(index.params, function(param, values) {
            state[param] = values;

            if (values.length > 1 && param !== 'machine') {
                var panel = $('<div class="panel  panel-default"/>');
                nav.append(panel);
                var panel_header = $('<div class="panel-heading">' + param + '</div>');
                panel.append(panel_header);
                var panel_body = $('<div class="panel-body"/>');
                panel.append(panel_body);
                var buttons = $('<div class="btn-group btn-group-justified" data-toggle="buttons"/>');
                panel_body.append(buttons);
                $.each(values, function(i, value) {
                    var value_display;
                    if (!value)
                        value_display = '[none]';
                    else
                        value_display = value;

                    var button = $('<a class="btn btn-default btn-xs active" role="button">' + value_display + '</a>');
                    buttons.append(button);

                    if (values.length > 1) {
                        button.on('click', function(evt) {
                            if (!evt.target.classList.contains("active")) {
                                state[param].push(value);
                            } else {
                                state[param] = arr_remove_from(state[param], value);
                            }
                            replace_graphs();
                        });
                    }
                });
            }
        });

        var panel = $('<div class="panel  panel-default"/>');
        nav.append(panel);
        var panel_header = $('<div class="panel-heading">test</div>');
        panel.append(panel_header);
        var panel_body = $('<div class="panel-body"/>');
        panel.append(panel_body);
        var buttons = $('<div class="btn-group-vertical" style="width: 100%" data-toggle="buttons"/>');
        panel_body.append(buttons);
        $.each(index.test_names, function(i, test_name) {
            var label = $('<label class="btn btn-default btn-xs"/>')
            buttons.append(label);
            var short_name = test_name.split(".");
            short_name = short_name[short_name.length - 1];
            var input = $('<input type="radio" name="options" id="option' + i + '">' + short_name + '</input>');
            label.append(input);
            label.on('change', function(evt) {
                if (!evt.target.classList.contains("active")) {
                    set_current_test(test_name);
                }
            });
            if (i == 0) {
                label.button('toggle');
            }
        });

        date_to_hash = index.date_to_hash;
        show_commit_url = index.show_commit_url;

        set_current_test(index.test_names[0]);
    }

    $.ajax({
        url: "index.json",
        cache: false
        }).done(setup);

    function set_current_test(test_name) {
        current_test = test_name;
        $("#title")[0].textContent = test_name;
        replace_graphs();
    }

    function collect_graphs() {
        function graph_to_path(test_name, state) {
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
            parts.push(test_name);
            return parts.join('/') + ".json";
        }

        function graph_label(state, differences) {
            var parts = [];
            $.each(state, function(key, value) {
                if (!(key === 'os' || key === 'cpu' || key === 'arch' || key === 'mem') &&
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

        function permutations(matrix) {
            if (obj_length(matrix) == 0) {
                return [{}];
            }

            var matrix = obj_copy(matrix);
            var key = get_first_key(matrix);
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

        if (current_test) {
            var graphs = permutations(state);
            var different = find_different_properties(graphs);
            var all = []

            $.each(graphs, function(i, graph) {
                all.push([graph_to_path(current_test, graph),
                          graph_label(graph, different)]);
            });
            return all;
        } else {
            return [];
        }
    };

    function replace_graphs() {
        graphs = [];
        update_graphs();

        to_load = collect_graphs();

        $.each(to_load, function(i, item) {
            console.log(item[0]);
            $.ajax({
                url: item[0],
            }).done(function(data) { add_graph(data, item[1]) });
        });
    };

    function add_graph(data, label) {
        graphs.push({
            data: data,
            label: label});
        update_graphs();
    }

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


        var plot = $.plot("#main-graph", graphs, options);

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
                    var githash = date_to_hash[x];
                    if (githash) {
                        previous_hash = githash;
		        showTooltip(
                            item.pageX, item.pageY,
                            pretty_second(y) + " @ " + githash.substring(0, 8));
                    }
		}
	    } else {
		$("#tooltip").remove();
		previous_point = null;
                previous_hash = null;
	    }
	});

        $("#main-graph").bind("plotclick", function (event, pos, item) {
            if (previous_hash) {
                window.open(show_commit_url + previous_hash, '_blank');
            }
	});

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
