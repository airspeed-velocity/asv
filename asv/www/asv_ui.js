'use strict';

$(document).ready(function() {
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

    function make_value_selector_panel(nav, heading, values, setup_callback) {
        var panel_body = make_panel(nav, heading);
        var vertical = false;
        var buttons = $('<div class="btn-group" ' +
                        'data-toggle="buttons"/>');

        panel_body.append(buttons);

        $.each(values, function (idx, value) {
            var button = $(
                '<a class="btn btn-default btn-xs active" role="button"/>');
            setup_callback(idx, value, button);
            buttons.append(button);
        });

        return panel_body;
    }

    function reflow_value_selector_panels() {
        $('.panel').each(function (i, panel_obj) {
            var panel = $(panel_obj);
            panel.find('.btn-group').each(function (i, buttons_obj) {
                var buttons = $(buttons_obj);
                var width = 0;

                if (buttons.hasClass('btn-group-vertical') ||
                    buttons.hasClass('btn-group-justified')) {
                    /* already processed */
                    return;
                }

                $.each(buttons.children(), function(idx, value) {
                    width += value.scrollWidth;
                });

                var vertical = (width >= panel_obj.clientWidth &&
                                panel_obj.clientWidth > 0);

                if (vertical) {
                    buttons.addClass("btn-group-vertical");
                    buttons.css("width", "100%");
                    buttons.css("max-height", "20ex");
                    buttons.css("overflow-y", "auto");
                }
                else {
                    buttons.addClass("btn-group-justified");
                }
            });
        });
    }

    function network_error(ajax, status, error) {
        $("#error-message").text(
            "Error fetching content. " +
            "Perhaps web server has gone down.");
        $("#error").modal('show');
    }

    /*
      Set up $.asv.ui
     */

    this.network_error = network_error;
    this.make_panel = make_panel;
    this.make_value_selector_panel = make_value_selector_panel;
    this.reflow_value_selector_panels = reflow_value_selector_panels;
    this.hover_graph = hover_graph;
    this.hover_summary_graph = hover_summary_graph;

    $.asv.ui = this;
});
