/* Сборка: экраны, выбор, выдача карточки.
   Ничего, кроме этого файла, страницу не двигает. */

(function () {
  'use strict';

  var cards = window.KOLODA || [];
  var $ = function (id) { return document.getElementById(id); };

  var current = null;        // показанная сейчас карточка
  var skipped = [];          // «другую» в этом заходе — чтобы не возвращать то же
  var weatherTags = null;
  var weatherPending = null;
  var previousScreen = 'start';
  var activeScreen = 'start';
  var placeOpen = false;     // раскрыт ли выбор места на стартовом экране

  /* «Зачем это» объясняет метод, а не результат: что считается выполненным
     и зачем режим устроен так. Оборот карточки сюда не попадает — иначе
     человек подтверждает подсказку вместо того, чтобы наблюдать. */
  var WHY = {
    'наружу': 'Задание уводит внимание с себя на то, что вокруг. Получилось — значит вы ' +
      'переключили фокус. Успех не в том, чтобы стало спокойнее.',
    'читать-место': 'Задание даёт признак, который сработает и на следующем доме, ' +
      'а не факт про этот.',
    'совместное-внимание': 'Задание строит общий фокус: взрослый называет, ребёнок ' +
      'подхватывает. Проверять ребёнка не нужно.',
    'с-собакой': 'Задание занимает паузу, которую она и так делает. Ничего ' +
      'дополнительного делать не надо.',
    'полевой-дневник': 'Одна фраза о том, что снаружи. Записи никто не читает ' +
      'и не оценивает.'
  };

  var MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];

  /* ————— экраны ————— */

  function show(name) {
    if (name !== 'archive' && name !== 'about') previousScreen = name;
    activeScreen = name;
    var list = document.querySelectorAll('.screen');
    for (var i = 0; i < list.length; i++) {
      var on = list[i].getAttribute('data-screen') === name;
      list[i].hidden = !on;
    }
    var focusable = document.querySelector('.screen:not([hidden]) [tabindex="-1"]');
    if (focusable) focusable.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }

  /* ————— тема ————— */

  function lightNow() {
    return Sun.category(new Date(), Store.state().place);
  }

  function applyTheme() {
    var setting = Store.state().theme || 'auto';
    var theme = setting;
    if (setting === 'auto') {
      var light = lightNow();
      if (light) {
        theme = (light === 'сумерки' || light === 'темнота') ? 'dark' : 'light';
      } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
        theme = 'light';
      } else {
        theme = 'dark';
      }
    }
    document.documentElement.setAttribute('data-theme', theme);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#141C26' : '#FFFFFF');
    mark('theme-list', 'themeSet', setting);
  }

  /* ————— выбор кнопками ————— */

  function mark(listId, key, value) {
    var box = $(listId);
    if (!box) return;
    var items = box.querySelectorAll('.option');
    for (var i = 0; i < items.length; i++) {
      items[i].setAttribute('aria-pressed', String(items[i].dataset[key]) === String(value));
    }
  }

  function renderStart() {
    var s = Store.state();
    mark('mode-list', 'mode', s.mode);
    mark('level-list', 'level', s.level);
    mark('age-list', 'age', s.age);
    $('sub-level').hidden = s.mode !== 'наружу';
    $('sub-age').hidden = s.mode !== 'совместное-внимание';
    $('btn-take').disabled = !s.mode;
    renderPlace();
  }

  function placeText() {
    var p = Store.state().place;
    if (!p) return 'Без места сайт работает, но различает только время года.';
    if (p.name) return 'Место: ' + p.name + '.';
    return 'Место определено по координатам.';
  }

  /* Когда место уже выбрано, блок сворачивается в одну строку:
     на телефоне стартовый экран и без того длинный. */
  function renderPlace() {
    var known = !!Store.state().place;
    $('place-state').textContent = placeText();
    $('about-place').textContent = placeText();
    $('btn-place-change').hidden = !known;
    $('place-actions').hidden = known && !placeOpen;
    if (known && !placeOpen) $('city-picker').hidden = true;
  }

  /* ————— погода ————— */

  function loadWeather() {
    var place = Store.state().place;
    weatherTags = null;
    weatherPending = Weather.load(place).then(function (tags) {
      weatherTags = tags;
      return tags;
    });
    return weatherPending;
  }

  function withWeather(done) {
    if (weatherTags || !weatherPending) { done(); return; }
    var settled = false;
    var go = function () { if (!settled) { settled = true; done(); } };
    weatherPending.then(go);
    setTimeout(go, 1200);      // ждать дольше, стоя на улице, незачем
  }

  /* ————— выдача ————— */

  function context() {
    var s = Store.state();
    var now = new Date();
    return {
      mode: s.mode,
      level: s.level,
      age: s.age,
      place: s.place,
      light: Sun.category(now, s.place),
      season: Sun.season(now),
      weather: weatherTags,
      seen: Store.seen(),
      sessions: s.sessions,
      today: Store.dayKey(now),
      recent: s.recent || [],
      exclude: skipped
    };
  }

  /* Подсказка раскрыта сразу на детских ступенях 2–3 и 4–5. */
  function alwaysOpenHint(card) {
    if (card.hintAlwaysVisible) return true;
    if (card.mode !== 'совместное-внимание') return false;
    return card.age === '2-3' || card.age === '4-5';
  }

  function showCard(card) {
    current = card;
    var hint = $('card-hint');
    var why = $('card-why');
    why.open = false;                  // состояние не запоминается: каждый раз свёрнут
    var box = $('card-text');
    box.classList.remove('fresh');
    void box.offsetWidth;            // перезапустить проявление текста
    box.classList.add('fresh');
    if (!card) {
      box.textContent =
        'Для этого света и времени года карточки нет. Подойдёт другой режим.';
      hint.hidden = true;
      why.hidden = true;
      $('btn-done').hidden = true;
      $('btn-another').textContent = 'К выбору режима';
      show('card');
      return;
    }
    box.textContent = card.text;
    $('btn-done').hidden = false;
    $('btn-another').textContent = 'Другую';
    $('why-criterion').textContent = card.criterion || '';
    $('why-done').hidden = !card.criterion;
    $('why-mode').textContent = WHY[card.mode] || '';
    why.hidden = false;
    if (card.fallback) {
      $('card-hint-text').textContent = card.fallback;
      /* С двухлетним читать некогда: пример нужен до попытки, а не после.
         Старшим ступеням подсказка по-прежнему под ссылкой. */
      hint.open = alwaysOpenHint(card);
      hint.hidden = false;
    } else {
      hint.hidden = true;
    }
    show('card');
  }

  function take(fresh) {
    if (fresh) skipped = [];
    Store.noteSession();
    withWeather(function () {
      var card = Deck.pick(cards, context());
      if (!card && skipped.length) {      // всё уже отложено — начать круг заново
        skipped = [];
        card = Deck.pick(cards, context());
      }
      if (card) Store.noteIssued(Deck.isSound(card));
      showCard(card);
    });
  }

  function another() {
    if (!current) { show('start'); return; }
    if (skipped.indexOf(current.id) < 0) skipped.push(current.id);
    take(false);
  }

  function done() {
    if (!current) return;
    Store.markSeen(current.id);
    if (Store.state().mode === 'полевой-дневник') {
      $('note-task').textContent = current.text;
      $('note-input').value = '';
      show('note');
      var field = $('note-input');
      if (field) setTimeout(function () { field.focus(); }, 60);
      return;
    }
    showBack();
  }

  /* Оборот и конец — один экран. Сверху задание мелко: человек ходил
     десять минут и успел забыть формулировку, а объяснение без неё повисает. */
  function showBack() {
    $('done-task').textContent = current ? current.text : '';
    $('back-title').textContent = current ? current.title : '';
    $('back-text').textContent = current ? current.back : '';
    show('back');
  }

  /* ————— дневник ————— */

  function renderArchive() {
    var list = Store.diary().slice().reverse();
    var box = $('archive-list');
    box.textContent = '';
    $('archive-empty').hidden = list.length > 0;
    for (var i = 0; i < list.length; i++) {
      var item = document.createElement('li');
      var when = document.createElement('time');
      var d = new Date(list[i].at);
      when.dateTime = list[i].day || '';
      when.textContent = d.getDate() + ' ' + MONTHS[d.getMonth()] + ' ' + d.getFullYear();
      var text = document.createElement('p');
      text.textContent = list[i].text;
      item.appendChild(when);
      item.appendChild(text);
      box.appendChild(item);
    }
  }

  /* ————— место ————— */

  function setPlace(place) {
    Store.patch({ place: place });
    placeOpen = false;
    renderPlace();
    applyTheme();
    loadWeather();
  }

  function askGeolocation() {
    if (!navigator.geolocation) { $('city-picker').hidden = false; return; }
    $('place-state').textContent = 'Определяю…';
    navigator.geolocation.getCurrentPosition(function (pos) {
      setPlace({ lat: pos.coords.latitude, lon: pos.coords.longitude, name: null, source: 'geo' });
    }, function () {
      renderPlace();
      $('city-picker').hidden = false;
      $('city-result').textContent = 'Не получилось. Выберите город.';
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 });
  }

  function chooseCity(key) {
    var c = Deck.CITIES[key];
    setPlace({
      lat: c.lat, lon: c.lon,
      name: key === 'мск' ? 'Москва' : 'Петербург',
      source: 'city'
    });
    $('city-picker').hidden = true;
    $('city-result').textContent = '';
  }

  /* ————— события ————— */

  function onClick(e) {
    var el = e.target.closest ? e.target.closest('[data-mode],[data-level],[data-age],[data-city],[data-theme-set],[data-go]') : null;
    if (!el) return;

    if (el.dataset.mode) {
      Store.patch({ mode: el.dataset.mode });
      renderStart();
      return;
    }
    if (el.dataset.level) {
      Store.patch({ level: parseInt(el.dataset.level, 10) });
      renderStart();
      return;
    }
    if (el.dataset.age) {
      Store.patch({ age: el.dataset.age });
      renderStart();
      return;
    }
    if (el.dataset.city) { chooseCity(el.dataset.city); return; }
    if (el.dataset.themeSet) {
      Store.patch({ theme: el.dataset.themeSet });
      applyTheme();
      return;
    }
    if (el.dataset.go) {
      var to = el.dataset.go;
      if (to === 'archive') renderArchive();
      if (to === 'return') to = previousScreen;
      if (to === 'start') renderStart();
      show(to);
    }
  }

  function bind() {
    document.addEventListener('click', onClick);

    $('btn-take').addEventListener('click', function () { take(true); });
    $('btn-done').addEventListener('click', done);
    $('btn-another').addEventListener('click', another);
    $('btn-more').addEventListener('click', function () { take(true); });

    $('btn-geo').addEventListener('click', askGeolocation);
    $('btn-city').addEventListener('click', function () {
      $('city-picker').hidden = !$('city-picker').hidden;
    });
    $('btn-place-change').addEventListener('click', function () {
      placeOpen = true;
      renderPlace();
      $('btn-geo').focus();
    });

    $('city-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var name = $('city-input').value.trim();
      if (!name) return;
      $('city-result').textContent = 'Ищу…';
      Weather.geocode(name).then(function (found) {
        if (!found) { $('city-result').textContent = 'Не нашлось.'; return; }
        setPlace({ lat: found.lat, lon: found.lon, name: found.name, source: 'city' });
        $('city-result').textContent = '';
        $('city-picker').hidden = true;
      });
    });

    $('note-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var text = $('note-input').value.trim();
      if (text) Store.addEntry(text.slice(0, 140), current ? current.id : null);
      showBack();
    });

    $('btn-wipe').addEventListener('click', function () {
      $('wipe-confirm').hidden = false;
    });
    $('btn-wipe-no').addEventListener('click', function () {
      $('wipe-confirm').hidden = true;
    });
    $('btn-wipe-yes').addEventListener('click', function () {
      Store.wipe();
      weatherTags = null;
      current = null;
      skipped = [];
      placeOpen = false;
      $('wipe-confirm').hidden = true;
      renderStart();
      applyTheme();
      show('start');
    });
  }

  function init() {
    applyTheme();
    renderStart();
    bind();
    loadWeather();
    if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0) {
      navigator.serviceWorker.register('sw.js').catch(function () { /* не критично */ });
    }
    /* Свет меняется, пока страница открыта: к вечеру тема должна догонять. */
    setInterval(function () {
      if (activeScreen === 'start' || activeScreen === 'back') applyTheme();
    }, 5 * 60 * 1000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
