'use strict';

// Polyfill for Object.keys
if (!Object.keys) {
  Object.keys = (function () {
    var hasOwnProperty = Object.prototype.hasOwnProperty,
        hasDontEnumBug = !({toString: null}).propertyIsEnumerable('toString'),
        dontEnums = [
          'toString',
          'toLocaleString',
          'valueOf',
          'hasOwnProperty',
          'isPrototypeOf',
          'propertyIsEnumerable',
          'constructor'
        ],
        dontEnumsLength = dontEnums.length;
 
    return function (obj) {
      if (typeof obj !== 'object' && typeof obj !== 'function' || obj === null) throw new TypeError('Object.keys called on non-object');
 
      var result = [];
 
      for (var prop in obj) {
        if (hasOwnProperty.call(obj, prop)) result.push(prop);
      }
 
      if (hasDontEnumBug) {
        for (var i=0; i < dontEnumsLength; i++) {
          if (hasOwnProperty.call(obj, dontEnums[i])) result.push(dontEnums[i]);
        }
      }
      return result;
    }
  })()
}

function sort_alpha(a,b) {
    return a.localeCompare(b);
}

$(document).ready(function() {
    var summary_loaded = false;
    var MAX_GRID_DEPTH = 3

    /* Callback a function when an element comes in view */
    function callback_in_view(element, func) {
        function handler(evt) {
            var visible = (
                $('#summarygrid-display').css('display') != 'none' &&
                (element.offset().top <= $(window).height() + $(window).scrollTop()) &&
                    (element.offset().top + element.height() >= $(window).scrollTop()));
            if (visible) {
                func();
                $(window).off('scroll', handler);
            }
        }
        $(window).on('scroll', handler);
    }

    function get_benchmarks_tree() {
        var master_json = $.asv.master_json;
        var groups_by_level = {};
        var current_object;
        
        $.each(master_json.benchmarks, function(bm_name, bm) {
            current_object = groups_by_level;
            for (var level = 0; level < MAX_GRID_DEPTH; level++) {
                var i = bm_name.indexOf('.');
                var nested = bm_name.slice(0, i);
                bm_name = bm_name.slice(i + 1)
                i = bm_name.indexOf('.');
                if (i === -1) {
                    if (!Array.isArray(current_object[nested])) {
                        current_object[nested] = []
                    }
                    current_object[nested].push(bm_name);
                    break;
                }
                if (current_object[nested] === undefined) {
                    current_object[nested] = {};
                    if (level === MAX_GRID_DEPTH - 1) {
                        current_object[nested] = []
                    }
                }
                if (level === MAX_GRID_DEPTH - 1) {
                    current_object[nested].push(bm_name);
                }
                current_object = current_object[nested]
            }
        });
        return groups_by_level;
    }

    function benchmark_container(bm) {
        var container = $(
            '<a class="btn benchmark-container" href="#' + bm.name +
            '"/>');
        var plot_div = $(
            '<div id="summarygrid-' + bm.name + '" class="benchmark-plot"/>');
        var display_name = bm.pretty_name || bm.name.slice(bm.name.indexOf('.') + 1);
        var name = $('<div class="benchmark-text">' + display_name + '</div>');
        name.tooltip({
            title: bm.name,
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

        callback_in_view(plot_div, function() {
            $.asv.load_graph_data(
                'graphs/summary/' + bm.name + '.json'
            ).done(function(data) {
                var options = {
                    colors: $.asv.colors,
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
        return container;
    }
    
    function benchmarks_tree_to_html(current_object, parent_container, bm_name, level) {
        if (Array.isArray(current_object)) {
            $.each(Array.from(current_object).sort(sort_alpha), function (i, bm_suffix) {
                var bm = $.asv.master_json.benchmarks[bm_name + '.' + bm_suffix];
                if (bm !== undefined) {
                    parent_container.append(benchmark_container(bm));
                }
            })
        }
        else {
            var sorted_keys = Object.keys(current_object).sort(sort_alpha);
            $.each(sorted_keys, function(i, key) {
                var new_bm_name = bm_name + '.' + key;
                var nested_container = $('<div class="benchmark-group-nested"/>');
                nested_container.append($('<h' + level + '>' + key + '</h' + level + '>'));

                var next_object = current_object[key]
                var inner = benchmarks_tree_to_html(
                    next_object,
                    nested_container,
                    new_bm_name,
                    level + 1
                );
                nested_container.append(inner);
                parent_container.append(nested_container);
            });
        }
    }
    function make_summary() {
        var summary_display = $('#summarygrid-display');
        var master_json = $.asv.master_json;
        var summary_container = $('<div/>');

        if (summary_loaded) {
            return;
        }
        var tree = get_benchmarks_tree();
        var sorted_keys = Object.keys(tree).sort(sort_alpha);
        $.each(sorted_keys, function(i, key) {
            if (tree.hasOwnProperty(key)) {
                var group_container = $('<div class="benchmark-group"/>')
                group_container.append($('<h1>' + key + '</h1>'));
                benchmarks_tree_to_html(tree[key], group_container, key, 2)

                summary_display.append(group_container);
            }
        });
        
        summary_display.append(summary_container);
        $(window).trigger('scroll');

        summary_loaded = true;
    }

    $.asv.register_page('', function(params) {
        $('#summarygrid-display').show();
        $("#title").text("All benchmarks");
        $('.tooltip').remove();
        make_summary();
    });
});
