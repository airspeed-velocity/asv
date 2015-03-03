$(document).ready(function() {
    function load_data() {
        var message = $("<div>Loading...</div>");
        $("#regressions-body").append(message);
        $.ajax({
            url: "regressions.json",
            cache: false
        }).done(function (data) {
            $("#regressions-body").empty();
            display_data(data);
        });
    }

    function display_data(data) {
        
    }

    /*
      Setup display hooks
    */
    $.asv.register_page('regressions', function() {
        $("#regressions-display").show()
        load_data();
    });
});
