/* Reset all trace opacities when mouse leaves the chart */
(function () {
    function attach() {
        var div = document.getElementById('main-chart');
        if (!div || typeof div.on !== 'function') {
            setTimeout(attach, 400);
            return;
        }

        /* remove any previous listener to avoid duplicates after re-renders */
        div.removeAllListeners('plotly_unhover');

        div.on('plotly_unhover', function () {
            if (!div.data || div.data.length === 0) return;
            var n = div.data.length;
            var opacities = [];
            var lineWidths = [];
            for (var i = 0; i < n; i++) {
                opacities.push(1.0);
                lineWidths.push(2.5);
            }
            Plotly.restyle(div, { opacity: opacities, 'line.width': lineWidths });
        });
    }

    /* attach on load, and re-attach whenever Dash re-renders the chart */
    document.addEventListener('DOMContentLoaded', function () {
        attach();
        /* watch for Dash replacing the chart node */
        var observer = new MutationObserver(function (mutations) {
            for (var m of mutations) {
                if (m.addedNodes.length) { attach(); break; }
            }
        });
        var container = document.getElementById('main-chart');
        if (container && container.parentNode) {
            observer.observe(container.parentNode, { childList: true, subtree: true });
        }
    });
})();
