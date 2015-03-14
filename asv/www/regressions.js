$(document).ready(function() {
    function load_data() {
        var message = $('<div>Loading...</div>');
        $('#regressions-body').append(message);
        $.ajax({
            url: 'regressions.json',
            cache: false
        }).done(function (data) {
            $('#regressions-body').empty();
            display_data(data);
        });
    }

    function display_data(data) {
        var body = $('#regressions-body');
        var display_table = $('<table class="table table-hover tablesorter"><thead><tr>' +
                              '<th>Benchmark</th>' +
                              '<th>Date</th>' +
                              '<th>Commit(s)</th>' +
                              '<th>Factor</th>' +
                              '<th>Best</th>' +
                              '<th>Current</th>' +
                              '</tr></thead></table>');
        var table_body = $('<tbody/>');

        var date_to_hash = data['date_to_hash'];
        var regressions = data['regressions'];

        $.each(regressions, function (benchmark_name, item) {
            var parameter_idx = item[0];
            var regression = item[1];

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
            var url_params = {time: [date_b]};;

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

            row.append($('<td/>').append(
                $('<a/>').attr('href', benchmark_url).text(benchmark_name)));
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
            var factor_link = $('<a/>').text(factor.toFixed(2) + 'x');
            row.append($('<td/>').append(factor_link));
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
                $.ajax({
                    url: 'graphs/summary/' + benchmark_basename + '.json',
                    cache: false
                }).done(function(data) {
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
                            markings: [
                                { color: '#d00', lineWidth: 2, xaxis: { from: date, to: date }}
                            ],
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

            factor_link.popover({
                placement: 'right auto',
                trigger: 'hover',
                html: true,
                delay: 50,
                content: $('<div/>').append(plot_div)
            });
            factor_link.on('show.bs.popover', update_plot);
        });

        display_table.append(table_body);
        body.append(display_table);

        $.tablesorter.addParser({
            id: 'factorSorter',
            is: function(s) { return false; },
            format: function(s) {  return s.replace(/x/, ''); },
            type: 'numeric'
        });

        $.tablesorter.addParser({
            id: 'benchmarkValueSorter',
            is: function(s) { return false; },
            format: function(s) {
                for (var k = 0; k < $.asv.time_units.length; ++k) {
                    var entry = $.asv.time_units[k];
                    m = s.match('^([0-9.]+)'+entry[0]+'$');
                    if (m) {
                        return parseFloat(m[1]) * entry[2] * 1e-30;
                    }
                }
                return s;
            },
            type: 'numeric'
        });

        display_table.tablesorter({
            headers: {
                1: { sorter: 'text' },
                3: { sorter: 'factorSorter' },
                4: { sorter: 'benchmarkValueSorter' },
                5: { sorter: 'benchmarkValueSorter' },
            }
        });
    }

    /*
      Setup display hooks
    */
    $.asv.register_page('regressions', function(params) {
        $("#title").text("Regressions");
        $('#regressions-display').show()
        load_data();
    });
});
