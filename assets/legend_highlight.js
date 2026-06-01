/*
 * Click legend items to highlight/dehighlight traces (multi-select).
 * - First click: highlight that trace, dim all others
 * - Click another: add to highlight group
 * - Click highlighted trace: remove from group
 * - If group becomes empty: reset all to normal
 */
(function () {
    var highlighted = new Set();   // trace indices currently highlighted

    function getDiv() {
        var outer = document.getElementById('main-chart');
        if (!outer) return null;
        var inner = outer.querySelector('.js-plotly-plot');
        return (inner && inner._fullData) ? inner : (outer._fullData ? outer : null);
    }

    function applyHighlight(div) {
        if (!div || !div.data) return;
        var n = div.data.length;
        if (highlighted.size === 0) {
            // reset all
            Plotly.restyle(div, { opacity: Array(n).fill(1.0), 'line.width': Array(n).fill(2.5) });
            return;
        }
        var opacities  = [];
        var lineWidths = [];
        for (var i = 0; i < n; i++) {
            var isHL = highlighted.has(i);
            opacities.push(isHL ? 1.0 : 0.1);
            lineWidths.push(isHL ? 3.5 : 2.0);
        }
        Plotly.restyle(div, { opacity: opacities, 'line.width': lineWidths });
    }

    function attach() {
        var div = getDiv();
        if (!div) { setTimeout(attach, 400); return; }
        if (div._rozaLegendAttached) return;
        div._rozaLegendAttached = true;

        div.on('plotly_legendclick', function (data) {
            var idx = data.curveNumber;
            if (highlighted.has(idx)) {
                highlighted.delete(idx);
            } else {
                highlighted.add(idx);
            }
            applyHighlight(div);
            return false;   // prevent Plotly's default show/hide
        });

        // reset highlighted set when figure is fully replaced
        div.on('plotly_react', function () {
            highlighted.clear();
        });
        div.on('plotly_newplot', function () {
            highlighted.clear();
        });
    }

    function watchForRender() {
        var wrapper = document.querySelector('.chart-wrapper');
        if (!wrapper) { setTimeout(watchForRender, 600); return; }
        new MutationObserver(function () {
            var div = getDiv();
            if (div) {
                div._rozaLegendAttached = false;
                highlighted.clear();
                attach();
            }
        }).observe(wrapper, { childList: true, subtree: true });
    }

    document.addEventListener('DOMContentLoaded', function () {
        attach();
        watchForRender();
    });
})();
