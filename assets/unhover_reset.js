/* Reset trace opacities when mouse leaves the Plotly chart.
   Dash wraps Plotly in an outer div (#main-chart).
   The actual Plotly plot lives in the inner .js-plotly-plot div.
*/
(function () {
    function getPlotlyDiv() {
        var outer = document.getElementById('main-chart');
        if (!outer) return null;
        // In Dash 2+/4+, the Plotly plot is the first child with _fullData
        var inner = outer.querySelector('.js-plotly-plot');
        return (inner && inner._fullData) ? inner : (outer._fullData ? outer : null);
    }

    function resetOpacity() {
        var div = getPlotlyDiv();
        if (!div || !div.data || div.data.length === 0) return;
        var n = div.data.length;
        Plotly.restyle(div,
            { opacity: Array(n).fill(1.0), 'line.width': Array(n).fill(2.5) }
        );
    }

    function attachUnhover() {
        var div = getPlotlyDiv();
        if (!div) { setTimeout(attachUnhover, 400); return; }
        if (div._rozaUnhoverAttached) return;
        div._rozaUnhoverAttached = true;

        div.on('plotly_unhover', resetOpacity);

        /* Backup: mouseleave on the nsewdrag SVG rect (the interactive layer) */
        var drag = div.querySelector('.nsewdrag');
        if (drag) {
            drag.addEventListener('mouseleave', resetOpacity);
        }
    }

    function watchForRender() {
        var wrapper = document.querySelector('.chart-wrapper');
        if (!wrapper) { setTimeout(watchForRender, 600); return; }
        var mo = new MutationObserver(function () {
            var div = getPlotlyDiv();
            if (div) { div._rozaUnhoverAttached = false; attachUnhover(); }
        });
        mo.observe(wrapper, { childList: true, subtree: true });
    }

    document.addEventListener('DOMContentLoaded', function () {
        attachUnhover();
        watchForRender();
    });
})();
