/* Отбор карточки.

   Порядок ровно такой, как в своде колоды:
   режим и ступень → свет → сезон → погода → смягчение погоды, если пул мал →
   недавно показанные и память о месте → случайная.

   Свет — жёсткий фильтр и не смягчается никогда: задание про оттенки серого
   в темноте физически невыполнимо. */

(function (global) {
  'use strict';

  var UNRELIABLE = ['ясно', 'свежий-снег', 'наст'];   // сервис отдаёт их неуверенно
  var MIN_POOL = 8;
  var REPEAT_DAYS = 7;
  var HISTORY_SESSIONS = 3;

  var CITIES = {
    'мск': { lat: 55.7558, lon: 37.6173, radius: 45, centerRadius: 5 },
    'спб': { lat: 59.9386, lon: 30.3141, radius: 40, centerRadius: 6 }
  };

  function distanceKm(a, b) {
    var R = 6371, rad = Math.PI / 180;
    var dLat = (b.lat - a.lat) * rad;
    var dLon = (b.lon - a.lon) * rad;
    var s = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(a.lat * rad) * Math.cos(b.lat * rad) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(s)));
  }

  function cityOf(place) {
    if (!place) return null;
    for (var key in CITIES) if (CITIES.hasOwnProperty(key)) {
      if (distanceKm(place, CITIES[key]) <= CITIES[key].radius) return key;
    }
    return null;
  }

  /* Грубое разделение: исторический центр или районы массовой застройки. */
  function inOldCenter(place) {
    var key = cityOf(place);
    if (!key) return false;
    return distanceKm(place, CITIES[key]) <= CITIES[key].centerRadius;
  }

  function has(list, value) { return !!list && list.indexOf(value) >= 0; }

  function lightFits(card, light) {
    if (!light) return true;                       // координат нет — по свету не судим
    if (has(card.light, 'неважно')) return true;   // в сумерках пул идёт вперемешку с этими
    return has(card.light, light);
  }

  function seasonFits(card, season) {
    if (!season) return true;
    return has(card.seasons, 'любой') || has(card.seasons, season);
  }

  function weatherFits(card, tags, relaxed) {
    if (!tags) return true;                        // погода не загрузилась
    if (has(card.weather, 'неважно')) return true;
    var need = card.weather;
    if (relaxed) {
      need = need.filter(function (t) { return UNRELIABLE.indexOf(t) < 0; });
      if (!need.length) return true;               // карта держалась только на ненадёжном
    }
    for (var i = 0; i < need.length; i++) if (has(tags, need[i])) return true;
    return false;
  }

  function modeFits(card, o) {
    if (card.mode !== o.mode) return false;
    if (o.mode === 'наружу') return card.level === o.level;
    if (o.mode === 'совместное-внимание') return card.age === o.age;
    if (o.mode === 'читать-место') {
      var city = cityOf(o.place);
      if (card.cityPack && card.cityPack !== city) return false;
      if (card.buildingType === 'исторический-центр' && !inOldCenter(o.place)) return false;
    }
    return true;
  }

  /* Пул после жёстких фильтров: режим, свет, сезон, погода. */
  function pool(cards, o) {
    var base = cards.filter(function (c) {
      return modeFits(c, o) && lightFits(c, o.light) && seasonFits(c, o.season);
    });
    var strict = base.filter(function (c) { return weatherFits(c, o.weather, false); });
    if (strict.length >= MIN_POOL || !o.weather) return strict;
    return base.filter(function (c) { return weatherFits(c, o.weather, true); });
  }

  function pick(cards, o) {
    var list = pool(cards, o);
    var seen = o.seen || {};
    var today = o.today;
    var skipped = o.exclude || [];

    if ((o.sessions || 0) < HISTORY_SESSIONS) {
      list = list.filter(function (c) { return !c.needsHistory; });
    }

    var fresh = list.filter(function (c) {
      if (skipped.indexOf(c.id) >= 0) return false;
      if (!seen[c.id]) return true;
      return Store.daysBetween(seen[c.id], today) > REPEAT_DAYS;
    });

    /* Пул бывает крошечным по существу: тёмным вечером у «Читать место»
       в неохваченном городе остаётся одна карта. Тогда семидневное правило
       уступает — берём ту, что не показывали дольше всех. */
    if (!fresh.length) {
      fresh = list.filter(function (c) { return skipped.indexOf(c.id) < 0; });
      if (!fresh.length) fresh = list;
      fresh.sort(function (a, b) {
        var da = seen[a.id] ? Store.daysBetween(seen[a.id], today) : 9999;
        var db = seen[b.id] ? Store.daysBetween(seen[b.id], today) : 9999;
        return db - da;
      });
      var oldest = fresh.length ? (seen[fresh[0].id] ? Store.daysBetween(seen[fresh[0].id], today) : 9999) : 0;
      fresh = fresh.filter(function (c) {
        var d = seen[c.id] ? Store.daysBetween(seen[c.id], today) : 9999;
        return d === oldest;
      });
    }

    if (!fresh.length) return null;
    return fresh[Math.floor(Math.random() * fresh.length)];
  }

  global.Deck = {
    pick: pick,
    pool: pool,
    cityOf: cityOf,
    inOldCenter: inOldCenter,
    distanceKm: distanceKm,
    CITIES: CITIES
  };
})(window);
