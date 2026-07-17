(function () {
    'use strict';

    // Confirmed real markup (verified directly from the live site):
    //   <input type="radio" class="radio-box__input"
    //          name="option_{attrId}_{salt}" value="{optionId}"
    //          data-user-value="14 mm" data-validation-name-label="Średnica">
    // Groups are simply "all radios sharing the same `name`" -- that's already how
    // the browser treats them as mutually exclusive, so we use `name` as the group key
    // rather than guessing at a wrapper element/class.

    let previousVisibleSets = new WeakMap();
    let lastHash = '';
    let autoSelectAttempts = 0;
    const MAX_AUTO_ATTEMPTS = 25;

    function allVariantRadios() {
        return Array.from(document.querySelectorAll('input.radio-box__input[type="radio"]'));
    }

    function groupIdFromName(name) {
        const m = name && name.match(/^option_(\d+)_/);
        return m ? m[1] : null;
    }

    function groupRadiosByName() {
        const groups = new Map(); // name -> [radios]
        allVariantRadios().forEach(radio => {
            if (!groups.has(radio.name)) groups.set(radio.name, []);
            groups.get(radio.name).push(radio);
        });
        return groups;
    }

    function parseNumber(str) {
        if (!str) return Infinity;
        const cleaned = str.replace(/[^0-9.,]/g, '').replace(',', '.').trim();
        const num = parseFloat(cleaned);
        return isNaN(num) ? Infinity : num;
    }

    function getSortKey(radio) {
        const val = radio.dataset.userValue || radio.value || '';
        return parseNumber(val);
    }

    function parseVariantOptionsHash() {
        const match = window.location.hash.match(/variantOptions=([^&]+)/);
        if (!match) return null;
        const selections = {};
        match[1].split(';').forEach(pair => {
            const [g, v] = pair.split(':');
            if (g && v) selections[g] = v;
        });
        return selections;
    }

    function getCurrentSelections() {
        const selections = {};
        groupRadiosByName().forEach((radios, name) => {
            const groupId = groupIdFromName(name);
            if (!groupId) return;
            const checked = radios.find(r => r.checked);
            if (checked) selections[groupId] = checked.value;
        });
        return selections;
    }

    function buildVariantHash(selections) {
        const keys = Object.keys(selections);
        if (keys.length === 0) return '';
        const parts = keys
            .sort((a, b) => a - b)
            .map(g => `${g}:${selections[g]}`);
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
        groupRadiosByName().forEach((radios, name) => {
            const groupId = groupIdFromName(name);
            if (!groupId || !selections[groupId]) return;

            const target = radios.find(r => r.value === String(selections[groupId]));
            if (target && !target.checked) {
                target.checked = true;
                ['change', 'input'].forEach(ev => target.dispatchEvent(new Event(ev, { bubbles: true })));
                applied = true;
            }
        });
        return applied;
    }

    function getVisibleRadios(radios) {
        return radios.filter(radio => {
            let el = radio;
            while (el && el !== document.body) {
                const style = getComputedStyle(el);
                if (el.hidden || style.display === 'none' || style.visibility === 'hidden') return false;
                el = el.parentElement;
            }
            return true;
        });
    }

    // Reorders the visible options for one group into ascending numeric order
    // (e.g. "8 mm, 10 mm, 12 mm, 14 mm" instead of admin-entry order).
    function sortVisibleOptions(visibleRadios) {
        if (visibleRadios.length < 2) return;
        // Each radio's own wrapper is the ".radio-box" div (confirmed markup);
        // its parent is the shared container we reorder children within.
        const wrappers = visibleRadios.map(r => r.closest('.radio-box') || r.parentElement);
        const parent = wrappers[0] && wrappers[0].parentElement;
        if (!parent) return;

        visibleRadios
            .map((radio, i) => ({ radio, wrapper: wrappers[i] }))
            .sort((a, b) => getSortKey(a.radio) - getSortKey(b.radio))
            .forEach(({ wrapper }) => {
                if (wrapper && wrapper.parentNode === parent) parent.appendChild(wrapper);
            });
    }

    function processGroup(name, radios) {
        const alreadyChosen = radios.some(r => r.checked);
        const visible = getVisibleRadios(radios);
        if (visible.length === 0) return false;

        const visibleIds = new Set(visible.map(r => r.id || r.value));
        const prev = previousVisibleSets.get(radios);
        const changed = !prev || prev.size !== visibleIds.size || ![...prev].every(id => visibleIds.has(id));
        previousVisibleSets.set(radios, visibleIds);

        sortVisibleOptions(visible);

        if (!alreadyChosen && visible.length === 1) {
            const target = visible[0];
            target.checked = true;
            ['change', 'input'].forEach(ev => target.dispatchEvent(new Event(ev, { bubbles: true })));
            return true;
        }
        return changed;
    }

    function checkAllGroups() {
        let didSomething = false;
        groupRadiosByName().forEach((radios, name) => {
            if (!groupIdFromName(name)) return; // skip anything that isn't a variant-option group
            if (processGroup(name, radios)) didSomething = true;
        });
        return didSomething;
    }

    function startAutoSelectLoop() {
        autoSelectAttempts = 0;
        const interval = setInterval(() => {
            autoSelectAttempts++;
            const didWork = checkAllGroups();
            updateURLHash();
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

        setTimeout(() => { checkAllGroups(); updateURLHash(); }, 800);
        setTimeout(() => { checkAllGroups(); updateURLHash(); }, 1800);
        setTimeout(() => { checkAllGroups(); updateURLHash(); }, 3500);

        setTimeout(startAutoSelectLoop, 1200);

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
        if (e.target.matches && e.target.matches('input.radio-box__input[type="radio"]')) {
            setTimeout(updateURLHash, 30);
        }
    });

    if (document.readyState !== 'loading') init();
    else document.addEventListener('DOMContentLoaded', init);
})();