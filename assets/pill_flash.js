/* Flash animation when clicking party or event pills */
document.addEventListener('click', function (e) {
    var btn = e.target.closest('.p-pill, .ev-pill');
    if (!btn) return;

    btn.classList.remove('pill-flash-anim');
    /* force reflow so removing+adding restarts animation */
    void btn.offsetWidth;
    btn.classList.add('pill-flash-anim');

    btn.addEventListener('animationend', function handler() {
        btn.classList.remove('pill-flash-anim');
        btn.removeEventListener('animationend', handler);
    });
}, true);
