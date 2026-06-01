/*
 * Animate chart traces when parties/blocs are added or removed.
 * - ADD:    the new trace flashes bright then settles
 * - REMOVE: a brief "collapse" ripple on the button that triggered removal
 */
(function () {
    var prevTraceNames = [];

    function getPlotlyDiv() {
        var outer = document.getElementById('main-chart');
        if (!outer) return null;
        var inner = outer.querySelector('.js-plotly-plot');
        return (inner && inner._fullData) ? inner : (outer._fullData ? outer : null);
    }

    /* Flash a single trace: brighten it, then restore */
    function flashTrace(div, traceIdx) {
        if (!div || traceIdx < 0 || traceIdx >= div.data.length) return;
        var n = div.data.length;

        // Step 1: dim everyone else, full-bright the new trace
        var opacities = Array(n).fill(0.08);
        opacities[traceIdx] = 1.0;
        Plotly.restyle(div, { opacity: opacities });

        // Step 2: after 350ms restore all to normal
        setTimeout(function () {
            Plotly.restyle(div, { opacity: Array(n).fill(1.0) });
        }, 380);
    }

    /* Called after every Dash figure update */
    function onFigureUpdate() {
        var div = getPlotlyDiv();
        if (!div || !div.data) return;

        var currentNames = div.data
            .filter(function (t) { return t.type === 'scatter' || t.type === 'bar'; })
            .map(function (t) { return t.name; });

        // Find newly added trace
        var added = currentNames.filter(function (n) { return prevTraceNames.indexOf(n) === -1; });

        if (added.length > 0) {
            var idx = currentNames.indexOf(added[0]);
            if (idx >= 0) flashTrace(div, idx);
        }

        prevTraceNames = currentNames.slice();
    }

    /* Watch for Plotly re-draws triggered by Dash */
    function attachPlotlyListener() {
        var div = getPlotlyDiv();
        if (!div) { setTimeout(attachPlotlyListener, 400); return; }
        if (div._rozaTraceFlashAttached) return;
        div._rozaTraceFlashAttached = true;

        div.on('plotly_afterplot', onFigureUpdate);
        // seed initial names
        prevTraceNames = (div.data || []).map(function (t) { return t.name; });
    }

    /* Re-attach after Dash re-renders the chart wrapper */
    function watchForRender() {
        var wrapper = document.querySelector('.chart-wrapper');
        if (!wrapper) { setTimeout(watchForRender, 600); return; }
        new MutationObserver(function () {
            var div = getPlotlyDiv();
            if (div) { div._rozaTraceFlashAttached = false; attachPlotlyListener(); }
        }).observe(wrapper, { childList: true, subtree: true });
    }

    document.addEventListener('DOMContentLoaded', function () {
        attachPlotlyListener();
        watchForRender();
    });
})();
