/* Общий хвост страниц с проверками.

   Страницы остаются читаемыми для человека: таблица «проверка — результат».
   Этот файл дополнительно кладёт в конец страницы тот же результат как JSON,
   который читает tests/run_tests.py, и ставит метку data-done у корня. */

(function (global) {
  'use strict';

  var STATUS = { ok: 'pass', no: 'fail', warn: 'warn', note: 'info' };

  function publish(container) {
    var root = typeof container === 'string' ? document.querySelector(container) : container;
    var rows = [];
    var count = { pass: 0, fail: 0, warn: 0, info: 0 };
    var section = '';

    var nodes = root.querySelectorAll('h2, tr');
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      if (node.tagName === 'H2') { section = node.textContent; continue; }
      var cells = node.children;
      if (cells.length < 2) continue;
      var status = STATUS[cells[1].className] || 'info';
      count[status]++;
      rows.push({
        section: section,
        name: cells[0].textContent.trim(),
        status: status,
        detail: cells[1].textContent.trim()
      });
    }

    var payload = JSON.stringify({
      title: document.title,
      passed: count.pass,
      failed: count.fail,
      warned: count.warn,
      info: count.info,
      rows: rows
    }).replace(/</g, '\\u003c');

    var tag = document.createElement('script');
    tag.type = 'application/json';
    tag.id = 'result';
    tag.textContent = payload;
    document.body.appendChild(tag);
    document.documentElement.setAttribute('data-done', '1');
    return count;
  }

  global.Report = { publish: publish };
})(window);
