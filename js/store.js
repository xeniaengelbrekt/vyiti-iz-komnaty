/* Хранение. Только localStorage, ничего не уходит наружу.
   Любая ошибка доступа (приватный режим, запрет на данные сайтов)
   не должна ломать страницу: сайт продолжает работать без памяти. */

(function (global) {
  'use strict';

  var PREFIX = 'vyiti:';
  var K_STATE = PREFIX + 'state';
  var K_SEEN = PREFIX + 'seen';
  var K_DIARY = PREFIX + 'diary';
  var K_WEATHER = PREFIX + 'weather';
  var SEEN_KEEP_DAYS = 30;

  function read(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) { return fallback; }
  }

  function write(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; }
    catch (e) { return false; }
  }

  function dayKey(date) {
    var d = date || new Date();
    var m = d.getMonth() + 1, n = d.getDate();
    return d.getFullYear() + '-' + (m < 10 ? '0' : '') + m + '-' + (n < 10 ? '0' : '') + n;
  }

  function daysBetween(a, b) {
    return Math.round((Date.parse(b + 'T00:00:00') - Date.parse(a + 'T00:00:00')) / 86400000);
  }

  var defaults = {
    mode: null,
    level: 1,
    age: '4-5',
    theme: 'auto',
    place: null,      // {lat, lon, name, source: 'geo' | 'city'}
    sessions: 0,
    lastDay: null
  };

  function state() {
    var s = read(K_STATE, null) || {};
    var out = {};
    for (var k in defaults) if (defaults.hasOwnProperty(k)) {
      out[k] = s.hasOwnProperty(k) ? s[k] : defaults[k];
    }
    return out;
  }

  function patch(fields) {
    var s = state();
    for (var k in fields) if (fields.hasOwnProperty(k)) s[k] = fields[k];
    write(K_STATE, s);
    return s;
  }

  /* Показанные карточки: {id: 'ГГГГ-ММ-ДД'}. Старше месяца не храним. */
  function seen() {
    var raw = read(K_SEEN, {}) || {};
    var today = dayKey();
    var out = {}, changed = false;
    for (var id in raw) if (raw.hasOwnProperty(id)) {
      if (daysBetween(raw[id], today) <= SEEN_KEEP_DAYS) out[id] = raw[id];
      else changed = true;
    }
    if (changed) write(K_SEEN, out);
    return out;
  }

  function markSeen(id) {
    var s = seen();
    s[id] = dayKey();
    write(K_SEEN, s);
  }

  /* Сессия — календарный день, в который была взята хотя бы одна карточка.
     Число сессий нужно ровно для одного: карточки, требующие памяти о месте,
     не выдаются первые три раза. Пользователю оно нигде не показывается. */
  function noteSession() {
    var s = state();
    var today = dayKey();
    if (s.lastDay === today) return s.sessions;
    var n = (s.sessions || 0) + 1;
    patch({ sessions: n, lastDay: today });
    return n;
  }

  function diary() { return read(K_DIARY, []) || []; }

  function addEntry(text, cardId) {
    var list = diary();
    list.push({ at: Date.now(), day: dayKey(), card: cardId || null, text: text });
    write(K_DIARY, list);
  }

  function wipe() {
    try {
      localStorage.removeItem(K_STATE);
      localStorage.removeItem(K_SEEN);
      localStorage.removeItem(K_DIARY);
      localStorage.removeItem(K_WEATHER);
    } catch (e) { /* нечего чистить */ }
  }

  global.Store = {
    state: state,
    patch: patch,
    seen: seen,
    markSeen: markSeen,
    noteSession: noteSession,
    diary: diary,
    addEntry: addEntry,
    wipe: wipe,
    dayKey: dayKey,
    daysBetween: daysBetween
  };
})(window);
