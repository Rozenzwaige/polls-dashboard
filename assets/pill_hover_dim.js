/* Dim all chart lines except the hovered party button's line */
(function () {
    function getDiv() {
        var outer = document.getElementById('main-chart');
        if (!outer) return null;
        var inner = outer.querySelector('.js-plotly-plot');
        return (inner && inner._fullData) ? inner : (outer._fullData ? outer : null);
    }

    function dimAllExcept(partyName) {
        var div = getDiv();
        if (!div || !div.data || div.data.length === 0) return;
        var n = div.data.length;
        var opacities = [];
        for (var i = 0; i < n; i++) {
            var traceName = div.data[i].name || '';
            opacities.push(traceName === partyName ? 1.0 : 0.08);
        }
        Plotly.restyle(div, { opacity: opacities });
    }

    function resetAll() {
        var div = getDiv();
        if (!div || !div.data || div.data.length === 0) return;
        Plotly.restyle(div, { opacity: Array(div.data.length).fill(1.0) });
    }

    function attach() {
        document.addEventListener('mouseover', function (e) {
            var btn = e.target.closest('.p-pill[data-party-name]');
            if (!btn) return;
            dimAllExcept(btn.getAttribute('data-party-name'));
        });

        document.addEventListener('mouseout', function (e) {
            var btn = e.target.closest('.p-pill[data-party-name]');
            if (!btn) return;
            // Only reset if not moving to another pill
            var to = e.relatedTarget && e.relatedTarget.closest('.p-pill[data-party-name]');
            if (!to) resetAll();
        });
    }

    document.addEventListener('DOMContentLoaded', attach);
})();
