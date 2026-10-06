/* Своё, без библиотек. Кладёт в кэш оболочку и колоду, чтобы сайт
   открывался без сети. Запросы погоды не кэшируются и в офлайне просто
   не проходят — отбор тогда идёт по свету и сезону. */

var CACHE = 'vyiti-12';
var SHELL = [
  './',
  'index.html',
  'styles.css',
  'cards.js',
  'js/sun.js',
  'js/weather.js',
  'js/store.js',
  'js/deck.js',
  'js/app.js',
  'manifest.webmanifest',
  'icons/icon.svg',
  'icons/icon-192.png',
  'icons/icon-512.png',
  'icons/apple-touch-icon.png'
];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) {
    return c.addAll(SHELL);
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.map(function (k) {
      return k === CACHE ? null : caches.delete(k);
    }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  /* Страницы самопроверки и тестов должны показывать текущую сборку, а не вчерашнюю. */
  if (url.pathname.indexOf('/tools/') >= 0 || url.pathname.indexOf('/tests/') >= 0) return;

  /* Отдаём из кэша сразу — на улице связь бывает никакая, — а следом
     тихо обновляем кэш. Обновлённая версия доедет со следующим открытием. */
  e.respondWith(
    caches.match(req).then(function (hit) {
      var fresh = fetch(req).then(function (res) {
        if (res && res.ok) {
          var copy = res.clone();
          caches.open(CACHE).then(function (c) { c.put(req, copy); });
        }
        return res;
      }).catch(function () {
        return hit || caches.match('index.html');
      });
      return hit || fresh;
    })
  );
});
