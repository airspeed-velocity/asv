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
        var display_table = $('<table class="table tablesorter"><thead><tr>' +
                              '<th>Benchmark</th>' +
                              '<th>Date</th>' +
                              '<th>Commit</th>' +
                              '<th>Factor</th>' +
                              '<th>Old value</th>' +
                              '<th>New value</th>' +
                              '</tr></thead></table>');
        var table_body = $('<tbody/>');

        var date_to_hash = data['date_to_hash'];
        var regressions = data['regressions'];

        $.each(regressions, function (benchmark_name, item) {
            var parameter_idx = item[0];
            var benchmark_url = '#' + benchmark_name.replace(/\(.*/, '') + '-' + parameter_idx;
            $.each(item[1], function (idx, regression_item) {
                var date = regression_item[0];
                var old_value = regression_item[1];
                var new_value = regression_item[2];
                var factor = new_value / old_value;
                var commit = $.asv.master_json.date_to_hash[date];
                var date_fmt = new Date(date);
                var commit_url = $.asv.master_json.show_commit_url + commit;

                var row = $('<tr/>');
                var item;

                item = $('<td/>');
                item.text(benchmark_name);
                row.append($('<td/>').append(
                        $('<a/>').attr('href', benchmark_url + '@' + date).text(benchmark_name)));
                row.append($('<td/>').text(date_fmt.toUTCString()));
                row.append($('<td/>').append(
                        $('<a/>').attr('href', commit_url).text(commit)));
                row.append($('<td/>').text(factor.toFixed(2) + "x"));
                row.append($('<td/>').text(old_value.toFixed(4)));
                row.append($('<td/>').text(new_value.toFixed(4)));

                table_body.append(row);
            });
        });

        display_table.append(table_body);
        body.append(display_table);
        display_table.tablesorter();
    }

    /*
      Setup display hooks
    */
    $.asv.register_page('regressions', function() {
        $("#title").text("Regressions");
        $('#regressions-display').show()
        load_data();
    });
});
