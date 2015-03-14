$(document).ready(function() {
    var regression_data = null;

    function load_data(params) {
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
                $('#regressions-body').empty();
                display_data(data, params);
            });
        }
    }

    function display_data(data, params) {
        var body = $('#regressions-body');
        var display_table = $('<table id="#regressions-table" class="table table-hover tablesorter"><thead><tr>' +
                              '<th data-sort="string">Benchmark</th>' +
                              '<th data-sort="string">Date</th>' +
                              '<th data-sort="string">Commit(s)</th>' +
                              '<th data-sort="factor">Factor</th>' +
                              '<th data-sort="value">Best</th>' +
                              '<th data-sort="value">Current</th>' +
                              '</tr></thead></table>');
        var table_body = $('<tbody/>');

        var date_to_hash = data['date_to_hash'];
        var regressions = data['regressions'];

        $.each(regressions, function (benchmark_name, item) {
            var graph_url = item[0];
            var param_dict = item[1];
            var parameter_idx = item[2];
            var regression = item[3];

            if (regression === null) {
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
                if ($.asv.master_json.show_commit_url.match(/.*\/\/github.com\//)) {
                    var commit_url = ($.asv.master_json.show_commit_url + '../compare/'
                                      + commit_a + '...' + commit_b);
                    row.append($('<td/>').append(
                        $('<a/>').attr('href', commit_url).text(commit_a + '..' + commit_b)));
                }
                else {
                    row.append($('<td/>').text(commit_a + '..' + commit_b));
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
            table_body.append(row);

            /* Show the summary graph as a popup */
            var plot_div = $('<div/>');
            plot_div.css('width', '11.8em');
            plot_div.css('height', '7em');
            plot_div.css('border', '2px solid black');
            plot_div.css('background-color', 'white');

            function update_plot() {
                markings = [
                    { color: '#d00', lineWidth: 2, xaxis: { from: date_b, to: date_b }}
                ];
                if (date_a !== null) {
                    markings.push({ color: '#d00', lineWidth: 2, xaxis: { from: date_a, to: date_a }});
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
        body.append(display_table);

        display_table.stupidtable({
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

        display_table.bind('aftertablesort', function (event, data) {
            var info = $.asv.parse_hash_string(window.location.hash);
            info.params['sort'] = [data.column];
            info.params['dir'] = [data.direction];
            window.location.hash = $.asv.format_hash_string(info);

            /* Update appearance */
            display_table.find('thead th').removeClass('asc');
            display_table.find('thead th').removeClass('desc');
            var th_to_sort = display_table.find("thead th").eq(parseInt(data.column));
            if (th_to_sort) {
                th_to_sort.addClass(data.direction);
            }
        });

        if (params.sort && params.dir) {
            var th_to_sort = display_table.find("thead th").eq(parseInt(params.sort[0]));
            th_to_sort.stupidsort(params.dir[0]);
        }
        else {
            var th_to_sort = display_table.find("thead th").eq(0);
            th_to_sort.stupidsort();
        }
    }

    /*
      Setup display hooks
    */
    $.asv.register_page('regressions', function(params) {
        $("#title").text("Regressions");
        $('#regressions-display').show()
        load_data(params);
    });
});
