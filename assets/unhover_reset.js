/* Reset all trace opacities when mouse leaves the chart area */
(function () {
    var NORMAL_OPACITY = 1.0;
    var NORMAL_WIDTH   = 2.5;

    function resetChart(div) {
        if (!div || !div.data || div.data.length === 0) return;
        var n = div.data.length;
        var opacities  = Array(n).fill(NORMAL_OPACITY);
        var lineWidths = Array(n).fill(NORMAL_WIDTH);
        Plotly.restyle(div, { opacity: opacities, 'line.width': lineWidths });
    }

    function attach(div) {
        if (!div || div._unhoverBound) return;
        div._unhoverBound = true;

        /* Plotly event — fires when cursor leaves a trace */
        div.on('plotly_unhover', function () { resetChart(div); });

        /* Fallback: DOM mouseleave on the SVG layer */
        var svg = div.querySelector('.nsewdrag, .js-plotly-plot');
        if (svg) {
            svg.addEventListener('mouseleave', function () { resetChart(div); });
        }
    }

    function tryAttach() {
        var div = document.getElementById('main-chart');
        if (div && typeof Plotly !== 'undefined' && div.data) {
            attach(div);
        } else {
            setTimeout(tryAttach, 300);
        }
    }

    /* Re-attach after every Dash re-render (Dash replaces inner DOM) */
    function watchForRerender() {
        var wrapper = document.querySelector('.chart-wrapper');
        if (!wrapper) { setTimeout(watchForRerender, 500); return; }

        var observer = new MutationObserver(function () {
            var div = document.getElementById('main-chart');
            if (div) { div._unhoverBound = false; tryAttach(); }
        });
        observer.observe(wrapper, { childList: true, subtree: true });
    }

    document.addEventListener('DOMContentLoaded', function () {
        tryAttach();
        watchForRerender();

        /* Hard fallback: mouseleave on the chart container div */
        document.addEventListener('mouseleave', function (e) {
            var div = document.getElementById('main-chart');
            if (!div) return;
            if (!div.contains(e.relatedTarget)) {
                resetChart(div);
            }
        }, true);
    });
})();
