(function () {
    'use strict';

    const CONTAINER_SEL = 'product-variants[module-instance-id="406"], [data-module-name="product_variants"], .product-variants';
    let previousVisibleSets = new WeakMap();
    let lastHash = '';
    let autoSelectAttempts = 0;
    const MAX_AUTO_ATTEMPTS = 25;

    function parseNumber(str) {
        if (!str) return Infinity;
        const cleaned = str.replace(/[^0-9.,]/g, '').replace(',', '.').trim();
        const num = parseFloat(cleaned);
        return isNaN(num) ? Infinity : num;
    }

    function getSortKey(radio) {
        let val = radio.dataset.userValue || radio.nextElementSibling?.textContent?.trim() || radio.value || '';
        return parseNumber(val);
    }

    function parseVariantOptionsHash() {
        const match = window.location.hash.match(/variantOptions=([^&]+)/);
        if (!match) return null;
        const selections = {};
        match[1].split(';').forEach(pair => {
            const [g, v] = pair.split(':').map(Number);
            if (g && v) selections[g] = v;
        });
        return selections;
    }

    function getCurrentSelections() {
        const selections = {};
        document.querySelectorAll('radio-variant-option, .variant-option, [data-variant-group]').forEach(group => {
            const checked = group.querySelector('input[type="radio"]:checked');
            if (!checked) return;

            const groupId = parseInt(group.dataset.groupId || group.id?.match(/\d+/)?.[0] || 0);
            const valueId = parseInt(checked.value || checked.dataset.value);

            if (groupId && valueId) selections[groupId] = valueId;
        });
        return selections;
    }

    function buildVariantHash(selections) {
        if (Object.keys(selections).length === 0) return '';
        const parts = Object.entries(selections)
            .sort((a, b) => a[0] - b[0])
            .map(([g, v]) => `${g}:${v}`);
        return `variantOptions=${parts.join(';')}`;
    }

    function updateURLHash() {
        const selections = getCurrentSelections();
        const newHash = buildVariantHash(selections);
        if (newHash === lastHash) return;
        lastHash = newHash;
        const url = new URL(window.location);
        url.hash = newHash ? '#' + newHash : '';
        window.history.replaceState(null, '', url);
    }

    function applyHashSelections(selections) {
        if (!selections) return false;
        let applied = false;
        document.querySelectorAll('radio-variant-option, .variant-option, [data-variant-group]').forEach(group => {
            const groupId = parseInt(group.dataset.groupId || group.id?.match(/\d+/)?.[0] || 0);
            if (!groupId || !selections[groupId]) return;

            const targetRadio = group.querySelector(`input[type="radio"][value="${selections[groupId]}"], input[type="radio"][data-value="${selections[groupId]}"]`);
            if (targetRadio && !targetRadio.checked) {
                targetRadio.checked = true;
                ['change', 'input'].forEach(ev => targetRadio.dispatchEvent(new Event(ev, { bubbles: true })));
                applied = true;
            }
        });
        return applied;
    }

    function isGroupTouched(group) {
        return !!group.querySelector('input[type="radio"]:checked');
    }

    function getVisibleRadios(group) {
        return Array.from(group.querySelectorAll('input[type="radio"]')).filter(radio => {
            let el = radio;
            while (el && el !== document.body) {
                const style = getComputedStyle(el);
                if (el.hidden || style.display === 'none' || style.visibility === 'hidden') return false;
                el = el.parentElement;
            }
            return true;
        });
    }

    function sortVisibleOptions(group, visibleRadios) {
        if (visibleRadios.length < 2) return false;
        const parent = visibleRadios[0].closest('[role="radiogroup"]') ||
            visibleRadios[0].closest('.control__element') ||
            visibleRadios[0].parentElement?.parentElement;
        if (!parent) return false;

        [...visibleRadios].sort((a, b) => getSortKey(a) - getSortKey(b))
            .forEach(radio => {
                const wrapper = radio.closest('.control') || radio.parentElement;
                if (wrapper && wrapper.parentNode === parent) parent.appendChild(wrapper);
            });
        return true;
    }

    function processGroup(group) {
        if (isGroupTouched(group)) return false;

        const visible = getVisibleRadios(group);
        if (visible.length === 0) return false;

        const visibleIds = new Set(visible.map(r => r.id));
        const prev = previousVisibleSets.get(group);
        const changed = !prev || prev.size !== visibleIds.size || ![...prev].every(id => visibleIds.has(id));

        previousVisibleSets.set(group, visibleIds);

        sortVisibleOptions(group, visible);

        if (visible.length === 1) {
            const target = visible[0];
            if (!target.checked) {
                target.checked = true;
                ['change', 'input'].forEach(ev => {
                    target.dispatchEvent(new Event(ev, { bubbles: true }));
                });
                return true;
            }
        }
        return changed;
    }

    function checkAllGroups() {
        const container = document.querySelector(CONTAINER_SEL);
        if (!container) return false;

        const groups = container.querySelectorAll('radio-variant-option, .variant-option, [data-variant-group]');
        let didSomething = false;

        groups.forEach(group => {
            if (processGroup(group)) didSomething = true;
        });

        return didSomething;
    }

    function startAutoSelectLoop() {
        autoSelectAttempts = 0;

        const interval = setInterval(() => {
            autoSelectAttempts++;
            const didWork = checkAllGroups();
            updateURLHash();

            // Stop if nothing changed for a few cycles or max attempts reached
            if ((!didWork && autoSelectAttempts > 8) || autoSelectAttempts > MAX_AUTO_ATTEMPTS) {
                clearInterval(interval);
            }
        }, 420);
    }

    function init() {
        const hashSelections = parseVariantOptionsHash();
        if (hashSelections) {
            setTimeout(() => applyHashSelections(hashSelections), 600);
        }

        // Initial runs
        setTimeout(() => { checkAllGroups(); updateURLHash(); }, 800);
        setTimeout(() => { checkAllGroups(); updateURLHash(); }, 1800);
        setTimeout(() => { checkAllGroups(); updateURLHash(); }, 3500);

        // Main persistent loop
        setTimeout(startAutoSelectLoop, 1200);

        // Mutation observer
        const observer = new MutationObserver(() => {
            clearTimeout(window.__autoVariantTimer);
            window.__autoVariantTimer = setTimeout(() => {
                checkAllGroups();
                updateURLHash();
            }, 150);
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['hidden', 'style', 'class', 'checked']
        });
    }

    document.addEventListener('change', e => {
        if (e.target.type === 'radio') {
            setTimeout(updateURLHash, 30);
        }
    });

    if (document.readyState !== 'loading') init();
    else document.addEventListener('DOMContentLoaded', init);
})();