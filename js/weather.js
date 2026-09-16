/* Погода: Open-Meteo, без ключа и без сторонних библиотек.
   Координаты округляются до сотых долей градуса (примерно километр)
   прежде, чем уйти в запрос.
   Если не загрузилось — молча возвращается null, отбор идёт по свету и сезону. */

(function (global) {
  'use strict';

  var API = 'https://api.open-meteo.com/v1/forecast';
  var GEO = 'https://geocoding-api.open-meteo.com/v1/search';
  var CACHE_KEY = 'vyiti:weather';
  var CACHE_MS = 30 * 60 * 1000;
  var TIMEOUT_MS = 6000;

  function round2(x) { return Math.round(x * 100) / 100; }

  function request(url) {
    if (typeof fetch !== 'function') return Promise.resolve(null);
    var ctrl = typeof AbortController === 'function' ? new AbortController() : null;
    var timer = setTimeout(function () { if (ctrl) ctrl.abort(); }, TIMEOUT_MS);
    return fetch(url, ctrl ? { signal: ctrl.signal } : undefined)
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; })
      .then(function (data) { clearTimeout(timer); return data; });
  }

  function buildUrl(lat, lon) {
    return API +
      '?latitude=' + round2(lat) + '&longitude=' + round2(lon) +
      '&current=temperature_2m,relative_humidity_2m,precipitation,cloud_cover,' +
      'wind_speed_10m,snow_depth' +
      '&hourly=temperature_2m,precipitation,snowfall,visibility' +
      '&wind_speed_unit=ms&past_days=1&forecast_days=1&timezone=auto';
  }

  function num(v) { return typeof v === 'number' && isFinite(v) ? v : null; }

  /* Индекс текущего часа в почасовом ряду. */
  function nowIndex(hourly, currentTime) {
    if (!hourly || !hourly.time || !hourly.time.length) return -1;
    var stamp = String(currentTime || '').slice(0, 13);
    for (var i = hourly.time.length - 1; i >= 0; i--) {
      if (String(hourly.time[i]).slice(0, 13) <= stamp) return i;
    }
    return -1;
  }

  function window_(arr, end, hours) {
    if (!arr) return [];
    var start = Math.max(0, end - hours + 1);
    var out = [];
    for (var i = start; i <= end && i < arr.length; i++) {
      if (typeof arr[i] === 'number' && isFinite(arr[i])) out.push(arr[i]);
    }
    return out;
  }

  function sum(a) { var s = 0; for (var i = 0; i < a.length; i++) s += a[i]; return s; }

  /* Из ответа сервиса — теги словаря погоды. Чистая функция, её же проверяют тесты. */
  function tags(data) {
    if (!data || !data.current) return null;

    var c = data.current;
    var h = data.hourly || {};
    var i = nowIndex(h, c.time);

    var temp = num(c.temperature_2m);
    var cloud = num(c.cloud_cover);
    var wind = num(c.wind_speed_10m);
    var precip = num(c.precipitation);
    var humid = num(c.relative_humidity_2m);
    var snowDepth = num(c.snow_depth);           // метры
    var snowCm = snowDepth === null ? null : snowDepth * 100;

    var temp24 = i >= 0 ? window_(h.temperature_2m, i, 24) : [];
    var precip3 = i >= 0 ? window_(h.precipitation, i - 1, 3) : [];
    var snow12 = i >= 0 ? window_(h.snowfall, i, 12) : [];
    var snow24 = i >= 0 ? window_(h.snowfall, i, 24) : [];
    var vis = i >= 0 && h.visibility ? num(h.visibility[i]) : null;

    var min24 = temp24.length ? Math.min.apply(null, temp24) : null;
    var max24 = temp24.length ? Math.max.apply(null, temp24) : null;
    var belowZero = 0;
    for (var k = 0; k < temp24.length; k++) if (temp24[k] < 0) belowZero++;

    var out = [];
    function add(t) { if (out.indexOf(t) < 0) out.push(t); }

    if (cloud !== null && cloud <= 35) add('ясно');
    if (cloud !== null && cloud >= 70) add('облачно');

    if (precip !== null) {
      if (precip > 0) {
        if (temp !== null && temp > 1) add('дождь');
        else add('снег');
      } else {
        add('сухо');
        if (temp !== null && temp > 1 && sum(precip3) > 0) add('после-дождя');
      }
    }

    if (temp !== null && temp <= -1) add('мороз');
    if (temp !== null && temp >= 0.5 && min24 !== null && min24 <= -2) add('оттепель');
    if (sum(snow12) >= 1 && max24 !== null && max24 <= 1) add('свежий-снег');
    if (snowCm !== null && snowCm >= 2 && sum(snow24) < 1 && belowZero >= 6) add('наст');
    if (wind !== null && wind >= 4.5) add('ветер');
    if ((vis !== null && vis < 1000) || (humid !== null && humid >= 97)) add('туман');

    return out;
  }

  function readCache(lat, lon) {
    try {
      var raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return null;
      var c = JSON.parse(raw);
      if (!c || c.lat !== round2(lat) || c.lon !== round2(lon)) return null;
      if (Date.now() - c.at > CACHE_MS) return null;
      return c.tags;
    } catch (e) { return null; }
  }

  function writeCache(lat, lon, value) {
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({
        lat: round2(lat), lon: round2(lon), at: Date.now(), tags: value
      }));
    } catch (e) { /* приватный режим или переполнение — не беда */ }
  }

  /* Теги погоды для координат. Всегда резолвится: null означает «не знаем». */
  function load(coords) {
    if (!coords) return Promise.resolve(null);
    var cached = readCache(coords.lat, coords.lon);
    if (cached) return Promise.resolve(cached);
    return request(buildUrl(coords.lat, coords.lon)).then(function (data) {
      var t = tags(data);
      if (t && t.length) writeCache(coords.lat, coords.lon, t);
      return t && t.length ? t : null;
    });
  }

  /* Поиск координат города по названию — тот же сервис, тоже без ключа. */
  function geocode(name) {
    var url = GEO + '?name=' + encodeURIComponent(name) +
              '&count=1&language=ru&format=json';
    return request(url).then(function (data) {
      if (!data || !data.results || !data.results.length) return null;
      var r = data.results[0];
      return { lat: r.latitude, lon: r.longitude, name: r.name };
    });
  }

  global.Weather = { load: load, tags: tags, geocode: geocode };
})(window);
