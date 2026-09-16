/* Высота солнца и категория света.
   Считается на клиенте, без обращения к сети.
   Алгоритм — низкоточная формула NOAA (погрешность порядка 0,01°),
   этого с запасом хватает для порогов 10°, 0° и −6°. */

(function (global) {
  'use strict';

  var RAD = Math.PI / 180;

  function mod(a, b) { return ((a % b) + b) % b; }

  /* Высота солнца над горизонтом в градусах.
     date — обычный Date, lat и lon — градусы, восточная долгота положительна. */
  function altitude(date, lat, lon) {
    var jd = date.getTime() / 86400000 + 2440587.5;
    var n = jd - 2451545.0;                                 // дней от J2000
    var L = mod(280.460 + 0.9856474 * n, 360);              // средняя долгота
    var g = mod(357.528 + 0.9856003 * n, 360) * RAD;        // средняя аномалия
    var lam = (L + 1.915 * Math.sin(g) + 0.020 * Math.sin(2 * g)) * RAD;
    var eps = (23.439 - 0.0000004 * n) * RAD;               // наклон эклиптики
    var alpha = Math.atan2(Math.cos(eps) * Math.sin(lam), Math.cos(lam));
    var dec = Math.asin(Math.sin(eps) * Math.sin(lam));
    var gmst = mod(18.697374558 + 24.06570982441908 * n, 24);
    var lst = (gmst * 15 + lon) * RAD;
    var H = lst - alpha;
    var h = Math.asin(Math.sin(lat * RAD) * Math.sin(dec) +
                      Math.cos(lat * RAD) * Math.cos(dec) * Math.cos(H));
    return h / RAD;
  }

  function categoryByAltitude(h) {
    if (h > 10) return 'день';
    if (h > 0) return 'низкое-солнце';
    if (h > -6) return 'сумерки';
    return 'темнота';
  }

  /* Категория света. Без координат вернуть null: гадать по часам нельзя,
     в ноябре и в июне одно и то же время означает разное. */
  function category(date, coords) {
    if (!coords) return null;
    return categoryByAltitude(altitude(date, coords.lat, coords.lon));
  }

  function season(date) {
    var m = date.getMonth() + 1;
    if (m === 12 || m <= 2) return 'зима';
    if (m <= 5) return 'весна';
    if (m <= 8) return 'лето';
    return 'осень';
  }

  global.Sun = {
    altitude: altitude,
    category: category,
    categoryByAltitude: categoryByAltitude,
    season: season
  };
})(window);
